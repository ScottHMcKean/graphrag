#!/usr/bin/env python3
"""
Streamlit App for Alberta Government Knowledge Graph Explorer
Interactive web interface for exploring the knowledge graph
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from knowledge_graph_visualizer import KnowledgeGraphVisualizer
import numpy as np
from collections import Counter
import networkx as nx

# Page configuration
st.set_page_config(
    page_title="Alberta Government Knowledge Graph Explorer",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown(
    """
<style>
    .main-header {
        font-size: 3rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .stSelectbox > div > div > select {
        background-color: white;
    }
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_data
def load_data():
    """Load and cache the knowledge graph data"""
    try:
        viz = KnowledgeGraphVisualizer()
        return viz
    except Exception as e:
        st.error(f"Error loading knowledge graph: {e}")
        return None


def main():
    # Header
    st.markdown(
        '<h1 class="main-header">🏛️ Alberta Government Knowledge Graph Explorer</h1>',
        unsafe_allow_html=True,
    )

    # Load data
    with st.spinner("Loading knowledge graph..."):
        viz = load_data()

    if viz is None:
        st.error("Failed to load knowledge graph data")
        return

    # Sidebar
    st.sidebar.title("🔍 Exploration Options")

    # Main navigation
    page = st.sidebar.selectbox(
        "Choose Analysis Type",
        [
            "📊 Overview Dashboard",
            "🌐 Network Visualization",
            "🔍 Entity Explorer",
            "📈 Analytics",
            "💡 Insights",
        ],
    )

    if page == "📊 Overview Dashboard":
        show_overview_dashboard(viz)
    elif page == "🌐 Network Visualization":
        show_network_visualization(viz)
    elif page == "🔍 Entity Explorer":
        show_entity_explorer(viz)
    elif page == "📈 Analytics":
        show_analytics(viz)
    elif page == "💡 Insights":
        show_insights(viz)


def show_overview_dashboard(viz):
    """Display the main overview dashboard"""
    st.header("📊 Knowledge Graph Overview")

    # Key Metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        type_col = "e.type" if "e.type" in viz.entities_df.columns else "type"
        st.metric(
            label="Total Entities",
            value=len(viz.entities_df),
            delta=f"{len(viz.entities_df[type_col].unique())} types",
        )

    with col2:
        st.metric(
            label="Total Relationships",
            value=len(viz.relationships_df),
            delta=f"{len(viz.relationships_df['relation'].unique())} types",
        )

    with col3:
        ministry_col = (
            "e.ministry" if "e.ministry" in viz.entities_df.columns else "ministry"
        )
        st.metric(
            label="Ministries Covered",
            value=len(viz.entities_df[ministry_col].unique()),
            delta="Government wide",
        )

    with col4:
        avg_connections = len(viz.relationships_df) / len(viz.entities_df) * 2
        st.metric(
            label="Avg Connections", value=f"{avg_connections:.1f}", delta="per entity"
        )

    # Charts Row 1
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Entity Type Distribution")
        fig_pie = viz.create_entity_type_distribution()
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        st.subheader("Entities by Ministry")
        fig_bar = viz.create_ministry_analysis()
        st.plotly_chart(fig_bar, use_container_width=True)

    # Recent Activity
    st.subheader("📋 Sample Entities by Type")

    # Handle column naming
    type_col = "e.type" if "e.type" in viz.entities_df.columns else "type"
    name_col = "e.name" if "e.name" in viz.entities_df.columns else "name"
    ministry_col = (
        "e.ministry" if "e.ministry" in viz.entities_df.columns else "ministry"
    )
    desc_col = (
        "e.description" if "e.description" in viz.entities_df.columns else "description"
    )

    entity_types = viz.entities_df[type_col].value_counts().head(5).index.tolist()

    for entity_type in entity_types:
        with st.expander(
            f"{entity_type} ({len(viz.entities_df[viz.entities_df[type_col] == entity_type])} entities)"
        ):
            sample_entities = viz.entities_df[
                viz.entities_df[type_col] == entity_type
            ].head(10)
            for _, entity in sample_entities.iterrows():
                st.write(f"• **{entity[name_col]}** ({entity[ministry_col]})")
                if pd.notna(entity[desc_col]) and entity[desc_col]:
                    st.write(f"  _{entity[desc_col][:100]}..._")


def show_network_visualization(viz):
    """Display interactive network visualization"""
    st.header("🌐 Interactive Network Graph")

    # Controls
    col1, col2, col3 = st.columns(3)

    with col1:
        max_nodes = st.slider("Maximum Nodes", 20, 200, 75)

    with col2:
        ministry_col = (
            "e.ministry" if "e.ministry" in viz.entities_df.columns else "ministry"
        )
        ministries = st.multiselect(
            "Filter by Ministry",
            options=viz.entities_df[ministry_col].unique(),
            default=[],
        )

    with col3:
        type_col = "e.type" if "e.type" in viz.entities_df.columns else "type"
        entity_types = st.multiselect(
            "Filter by Entity Type",
            options=viz.entities_df[type_col].unique(),
            default=[],
        )

    # Filter data if needed
    filtered_entities = viz.entities_df.copy()
    if ministries:
        filtered_entities = filtered_entities[
            filtered_entities[ministry_col].isin(ministries)
        ]
    if entity_types:
        filtered_entities = filtered_entities[
            filtered_entities[type_col].isin(entity_types)
        ]

    # Create network graph
    with st.spinner("Generating network visualization..."):
        fig = viz.create_network_graph(max_nodes=max_nodes)
        st.plotly_chart(fig, use_container_width=True)

    # Network Statistics
    st.subheader("📊 Network Statistics")
    col1, col2, col3 = st.columns(3)

    # Calculate network metrics
    G = nx.from_pandas_edgelist(viz.relationships_df, source="source", target="target")

    with col1:
        st.metric("Network Density", f"{nx.density(G):.3f}")

    with col2:
        if nx.is_connected(G):
            st.metric(
                "Average Path Length", f"{nx.average_shortest_path_length(G):.2f}"
            )
        else:
            st.metric("Connected Components", nx.number_connected_components(G))

    with col3:
        clustering = nx.average_clustering(G)
        st.metric("Clustering Coefficient", f"{clustering:.3f}")


def show_entity_explorer(viz):
    """Entity exploration interface"""
    st.header("🔍 Entity Explorer")

    # Handle column naming
    name_col = "e.name" if "e.name" in viz.entities_df.columns else "name"
    type_col = "e.type" if "e.type" in viz.entities_df.columns else "type"
    ministry_col = (
        "e.ministry" if "e.ministry" in viz.entities_df.columns else "ministry"
    )
    desc_col = (
        "e.description" if "e.description" in viz.entities_df.columns else "description"
    )
    source_col = (
        "e.source_document"
        if "e.source_document" in viz.entities_df.columns
        else "source_document"
    )

    # Entity search
    entity_names = viz.entities_df[name_col].unique()
    selected_entity = st.selectbox("Select an Entity to Explore", entity_names)

    if selected_entity:
        # Entity details
        entity_info = viz.entities_df[
            viz.entities_df[name_col] == selected_entity
        ].iloc[0]

        col1, col2 = st.columns([2, 1])

        with col1:
            st.subheader(f"📄 {selected_entity}")
            st.write(f"**Type:** {entity_info[type_col]}")
            st.write(f"**Ministry:** {entity_info[ministry_col]}")
            st.write(f"**Source:** {entity_info[source_col]}")
            if pd.notna(entity_info[desc_col]) and entity_info[desc_col]:
                st.write(f"**Description:** {entity_info[desc_col]}")

        with col2:
            # Entity connections count
            connections_df = viz.query_entity_connections(selected_entity)
            st.metric("Total Connections", len(connections_df))

            if not connections_df.empty:
                outgoing = len(
                    connections_df[connections_df["direction"] == "outgoing"]
                )
                incoming = len(
                    connections_df[connections_df["direction"] == "incoming"]
                )
                st.metric("Outgoing", outgoing)
                st.metric("Incoming", incoming)

        # Connections table
        if not connections_df.empty:
            st.subheader("🔗 Connected Entities")

            # Add filtering for connections
            col1, col2 = st.columns(2)
            with col1:
                direction_filter = st.selectbox(
                    "Filter by Direction", ["All", "Outgoing", "Incoming"]
                )
            with col2:
                relation_types = connections_df["relationship"].unique()
                relation_filter = st.selectbox(
                    "Filter by Relationship", ["All"] + list(relation_types)
                )

            # Apply filters
            filtered_connections = connections_df.copy()
            if direction_filter != "All":
                filtered_connections = filtered_connections[
                    filtered_connections["direction"] == direction_filter.lower()
                ]
            if relation_filter != "All":
                filtered_connections = filtered_connections[
                    filtered_connections["relationship"] == relation_filter
                ]

            # Display connections
            st.dataframe(
                filtered_connections[
                    ["connected_entity", "relationship", "direction", "source_document"]
                ],
                use_container_width=True,
            )
        else:
            st.info("No connections found for this entity.")


def show_analytics(viz):
    """Advanced analytics and insights"""
    st.header("📈 Knowledge Graph Analytics")

    # Relationship type analysis
    st.subheader("Relationship Type Analysis")
    rel_counts = viz.relationships_df["relation"].value_counts().head(15)

    fig = go.Figure(
        data=[
            go.Bar(
                x=rel_counts.values,
                y=rel_counts.index,
                orientation="h",
                marker_color="#45B7D1",
            )
        ]
    )

    fig.update_layout(
        title="Most Common Relationship Types",
        xaxis_title="Count",
        yaxis_title="Relationship Type",
        height=500,
    )

    st.plotly_chart(fig, use_container_width=True)

    # Most connected entities
    st.subheader("Most Connected Entities")

    # Calculate node degrees
    node_degrees = Counter()
    for _, row in viz.relationships_df.iterrows():
        node_degrees[row["source"]] += 1
        node_degrees[row["target"]] += 1

    top_entities = pd.DataFrame(
        [
            {
                "Entity": entity,
                "Connections": count,
                "Type": (
                    viz.entities_df[viz.entities_df["name"] == entity]["type"].iloc[0]
                    if len(viz.entities_df[viz.entities_df["name"] == entity]) > 0
                    else "Unknown"
                ),
            }
            for entity, count in node_degrees.most_common(20)
        ]
    )

    st.dataframe(top_entities, use_container_width=True)

    # Ministry comparison
    st.subheader("Ministry Comparison")

    ministry_stats = []
    for ministry in viz.entities_df["ministry"].unique():
        entities_count = len(viz.entities_df[viz.entities_df["ministry"] == ministry])
        relationships_count = len(
            viz.relationships_df[viz.relationships_df["ministry"] == ministry]
        )

        ministry_stats.append(
            {
                "Ministry": ministry,
                "Entities": entities_count,
                "Relationships": relationships_count,
                "Ratio": (
                    relationships_count / entities_count if entities_count > 0 else 0
                ),
            }
        )

    ministry_df = pd.DataFrame(ministry_stats).sort_values("Entities", ascending=False)
    st.dataframe(ministry_df, use_container_width=True)


def show_insights(viz):
    """Generate insights from the knowledge graph"""
    st.header("💡 Knowledge Graph Insights")

    # Key insights
    insights = []

    # Most connected entity
    node_degrees = Counter()
    for _, row in viz.relationships_df.iterrows():
        node_degrees[row["source"]] += 1
        node_degrees[row["target"]] += 1

    most_connected = node_degrees.most_common(1)[0]
    insights.append(
        f"🎯 **Most Connected Entity**: '{most_connected[0]}' with {most_connected[1]} connections"
    )

    # Most common entity type
    top_entity_type = viz.entities_df["type"].value_counts().iloc[0]
    insights.append(
        f"📊 **Dominant Entity Type**: '{viz.entities_df['type'].value_counts().index[0]}' ({top_entity_type} entities)"
    )

    # Most active ministry
    top_ministry = viz.entities_df["ministry"].value_counts().iloc[0]
    insights.append(
        f"🏛️ **Most Active Ministry**: '{viz.entities_df['ministry'].value_counts().index[0]}' ({top_ministry} entities)"
    )

    # Most common relationship
    top_relationship = viz.relationships_df["relation"].value_counts().iloc[0]
    insights.append(
        f"🔗 **Most Common Relationship**: '{viz.relationships_df['relation'].value_counts().index[0]}' ({top_relationship} occurrences)"
    )

    # Display insights
    for insight in insights:
        st.markdown(insight)
        st.markdown("---")

    # Search functionality
    st.subheader("🔍 Quick Search")
    search_term = st.text_input("Search for entities, relationships, or ministries:")

    if search_term:
        # Search entities
        entity_matches = viz.entities_df[
            viz.entities_df["name"].str.contains(search_term, case=False, na=False)
            | viz.entities_df["description"].str.contains(
                search_term, case=False, na=False
            )
        ]

        if not entity_matches.empty:
            st.write(f"**Found {len(entity_matches)} entity matches:**")
            for _, entity in entity_matches.head(10).iterrows():
                st.write(
                    f"• **{entity['name']}** ({entity['type']}) - {entity['ministry']}"
                )

        # Search relationships
        rel_matches = viz.relationships_df[
            viz.relationships_df["relation"].str.contains(
                search_term, case=False, na=False
            )
        ]

        if not rel_matches.empty:
            st.write(f"**Found {len(rel_matches)} relationship matches:**")
            unique_relations = rel_matches["relation"].unique()
            for relation in unique_relations[:10]:
                count = len(rel_matches[rel_matches["relation"] == relation])
                st.write(f"• **{relation}** ({count} occurrences)")


if __name__ == "__main__":
    main()
