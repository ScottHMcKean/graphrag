#!/usr/bin/env python3
"""
Test script to demonstrate the Knowledge Graph functionality
"""

from knowledge_graph_visualizer import KnowledgeGraphVisualizer
from knowledge_graph_queries import KnowledgeGraphQueries
import pandas as pd


def main():
    print("🏛️ Alberta Government Knowledge Graph - Demonstration")
    print("=" * 60)

    # Initialize visualizer
    viz = KnowledgeGraphVisualizer()

    if viz.entities_df is not None and viz.relationships_df is not None:
        print(f"✅ Successfully loaded knowledge graph data!")
        print(f"📊 Total Entities: {len(viz.entities_df)}")
        print(f"🔗 Total Relationships: {len(viz.relationships_df)}")

        # Show entity type distribution
        type_col = "e.type" if "e.type" in viz.entities_df.columns else "type"
        entity_types = viz.entities_df[type_col].value_counts()
        print(f"\n📈 Entity Types:")
        for entity_type, count in entity_types.head(10).items():
            print(f"   {entity_type}: {count}")

        # Show ministry distribution
        ministry_col = (
            "e.ministry" if "e.ministry" in viz.entities_df.columns else "ministry"
        )
        ministries = viz.entities_df[ministry_col].value_counts()
        print(f"\n🏛️ Top Ministries:")
        for ministry, count in ministries.head(5).items():
            print(f"   {ministry}: {count} entities")

        # Show most common relationships
        relationships = viz.relationships_df["relation"].value_counts()
        print(f"\n🔗 Most Common Relationships:")
        for relation, count in relationships.head(5).items():
            print(f"   {relation}: {count} occurrences")

        # Create and save network visualization
        print(f"\n🌐 Creating network visualization...")
        try:
            network_fig = viz.create_network_graph(max_nodes=50)
            network_fig.write_html("alberta_knowledge_graph.html")
            print(
                f"✅ Interactive network graph saved to 'alberta_knowledge_graph.html'"
            )
        except Exception as e:
            print(f"❌ Error creating visualization: {e}")

        # Test entity search
        print(f"\n🔍 Testing entity search functionality...")
        queries = KnowledgeGraphQueries()
        if queries.entities_df is not None:
            search_results = queries.search_entities("Adult Learning")
            if not search_results.empty:
                print(
                    f"✅ Found {len(search_results)} entities matching 'Adult Learning':"
                )
                for _, entity in search_results.head(3).iterrows():
                    print(
                        f"   • {entity['name']} ({entity['type']}) - {entity['ministry']}"
                    )
            else:
                print("❌ No search results found")

        # Test connection queries
        print(f"\n🔗 Testing connection queries...")
        name_col = "e.name" if "e.name" in viz.entities_df.columns else "name"
        sample_entity = viz.entities_df[name_col].iloc[0]
        connections = viz.query_entity_connections(sample_entity)
        if not connections.empty:
            print(f"✅ '{sample_entity}' has {len(connections)} connections:")
            for _, conn in connections.head(3).iterrows():
                print(
                    f"   • {conn['relationship']} → {conn['connected_entity']} ({conn['direction']})"
                )
        else:
            print(f"❌ No connections found for '{sample_entity}'")

        print(f"\n🎯 Knowledge Graph Insights:")
        print(f"   • Most Connected Entity: Based on relationship analysis")
        print(f"   • Cross-Ministry Relationships: Government-wide connections")
        print(f"   • Program Hierarchies: Structured policy implementation")
        print(f"   • Budget Allocations: Financial entity tracking")

        print(f"\n🚀 Ready for Interactive Exploration!")
        print(f"   Run: streamlit run streamlit_knowledge_graph_app.py")
        print(f"   View: Open 'alberta_knowledge_graph.html' in browser")

    else:
        print("❌ Failed to load knowledge graph data")
        print("   Make sure the CSV files exist in knowledge_graph_output/")


if __name__ == "__main__":
    main()
