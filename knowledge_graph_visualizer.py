#!/usr/bin/env python3
"""
Knowledge Graph Visualizer for Alberta Government Documents
Interactive visualization and exploration using Plotly and Kuzu
"""

import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import networkx as nx
import kuzu
from typing import Dict, List, Tuple, Optional
import logging
from collections import Counter, defaultdict
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KnowledgeGraphVisualizer:
    """Interactive visualizer for the Alberta Government Knowledge Graph"""

    def __init__(self, db_path: str = "alberta_knowledge_graph.db"):
        """Initialize the visualizer with CSV fallback (avoiding database segfault)"""
        self.db_path = db_path
        self.db = None
        self.conn = None
        self.entities_df = None
        self.relationships_df = None
        self._load_data()

    def _load_data(self):
        """Load data from CSV files (skipping database to avoid segfault)"""
        try:
            # Skip database loading due to segmentation fault issues
            logger.info("Loading data from CSV files directly")
            self._load_from_csv()

        except Exception as e:
            logger.error(f"Error loading data from CSV: {e}")
            # Create empty DataFrames as fallback
            self.entities_df = pd.DataFrame()
            self.relationships_df = pd.DataFrame()

    def _load_from_csv(self):
        """Fallback method to load from CSV files"""
        try:
            self.entities_df = pd.read_csv("knowledge_graph_output/entities.csv")

            # Load and parse triplets CSV
            triplets_df = pd.read_csv("knowledge_graph_output/triplets.csv")

            # Parse the triplet format "source | relation | target"
            parsed_triplets = []
            for _, row in triplets_df.iterrows():
                triplet = row["triplet"]
                parts = triplet.split(" | ")
                if len(parts) == 3:
                    parsed_triplets.append(
                        {
                            "source": parts[0].strip(),
                            "relation": parts[1].strip(),
                            "target": parts[2].strip(),
                            "source_document": row.get("r.source_document", ""),
                            "ministry": "Unknown",  # Will be filled later
                        }
                    )

            self.relationships_df = pd.DataFrame(parsed_triplets)

            # Now add ministry information
            if not self.relationships_df.empty and self.entities_df is not None:
                # Handle different column naming conventions
                name_col = "e.name" if "e.name" in self.entities_df.columns else "name"
                ministry_col = (
                    "e.ministry"
                    if "e.ministry" in self.entities_df.columns
                    else "ministry"
                )

                entity_ministry_map = dict(
                    zip(self.entities_df[name_col], self.entities_df[ministry_col])
                )
                self.relationships_df["ministry"] = (
                    self.relationships_df["source"]
                    .map(entity_ministry_map)
                    .fillna("Unknown")
                )

            logger.info("Loaded data from CSV files as fallback")
        except Exception as e:
            logger.error(f"Error loading CSV files: {e}")
            self.entities_df = None
            self.relationships_df = None

    def get_entity_statistics(self) -> Dict:
        """Get comprehensive statistics about entities"""
        if self.entities_df is None:
            return {}

        stats = {
            "total_entities": len(self.entities_df),
            "entity_types": self.entities_df["type"].value_counts().to_dict(),
            "entities_by_ministry": self.entities_df["ministry"]
            .value_counts()
            .to_dict(),
            "top_entities": self.entities_df["name"].value_counts().head(10).to_dict(),
        }
        return stats

    def get_relationship_statistics(self) -> Dict:
        """Get comprehensive statistics about relationships"""
        if self.relationships_df is None:
            return {}

        stats = {
            "total_relationships": len(self.relationships_df),
            "relation_types": self.relationships_df["relation"]
            .value_counts()
            .to_dict(),
            "relationships_by_ministry": self.relationships_df["ministry"]
            .value_counts()
            .to_dict(),
            "most_connected_entities": self._get_node_degrees(),
        }
        return stats

    def _get_node_degrees(self) -> Dict:
        """Calculate node degrees (connection counts)"""
        if self.relationships_df is None:
            return {}

        # Count connections for each entity
        source_counts = self.relationships_df["source"].value_counts()
        target_counts = self.relationships_df["target"].value_counts()

        # Combine source and target counts
        total_counts = source_counts.add(target_counts, fill_value=0)
        return total_counts.head(10).to_dict()

    def create_network_graph(self, max_nodes: int = 100) -> go.Figure:
        """Create an interactive network graph visualization"""

        # Get most connected entities
        node_degrees = Counter()
        for _, row in self.relationships_df.iterrows():
            node_degrees[row["source"]] += 1
            node_degrees[row["target"]] += 1

        # Limit to top nodes
        top_nodes = dict(node_degrees.most_common(max_nodes))

        # Filter relationships to only include top nodes
        graph_rels = self.relationships_df[
            (self.relationships_df["source"].isin(top_nodes))
            & (self.relationships_df["target"].isin(top_nodes))
        ]

        # Create NetworkX graph for layout
        G = nx.from_pandas_edgelist(
            graph_rels, source="source", target="target", create_using=nx.Graph()
        )

        # Calculate layout
        pos = nx.spring_layout(G, k=1, iterations=50)

        # Prepare node data
        node_names = list(G.nodes())
        node_x = [pos[node][0] for node in node_names]
        node_y = [pos[node][1] for node in node_names]

        # Get node colors based on entity types
        node_colors = []
        node_sizes = []
        node_text = []

        color_map = {
            "Program": "#FF6B6B",
            "Organization": "#4ECDC4",
            "Policy": "#45B7D1",
            "Location": "#96CEB4",
            "Person": "#FFEAA7",
            "Event": "#DDA0DD",
            "Document": "#98D8C8",
            "Budget": "#F7DC6F",
            "Legislation": "#BB8FCE",
        }

        # Handle different column naming conventions
        name_col = "e.name" if "e.name" in self.entities_df.columns else "name"
        type_col = "e.type" if "e.type" in self.entities_df.columns else "type"
        ministry_col = (
            "e.ministry" if "e.ministry" in self.entities_df.columns else "ministry"
        )
        desc_col = (
            "e.description"
            if "e.description" in self.entities_df.columns
            else "description"
        )

        for node in node_names:
            # Get entity info
            entity_info = self.entities_df[self.entities_df[name_col] == node]
            if not entity_info.empty:
                entity_type = entity_info.iloc[0][type_col]
                ministry = entity_info.iloc[0][ministry_col]

                node_colors.append(color_map.get(entity_type, "#95A5A6"))
                node_sizes.append(min(50, max(10, node_degrees[node] * 3)))
                node_text.append(
                    f"{node}<br>Type: {entity_type}<br>Ministry: {ministry}<br>Connections: {node_degrees[node]}"
                )
            else:
                node_colors.append("#95A5A6")
                node_sizes.append(20)
                node_text.append(f"{node}<br>Connections: {node_degrees[node]}")

        # Prepare edge data
        edge_x = []
        edge_y = []

        for _, row in graph_rels.iterrows():
            source, target = row["source"], row["target"]
            if source in pos and target in pos:
                edge_x.extend([pos[source][0], pos[target][0], None])
                edge_y.extend([pos[source][1], pos[target][1], None])

        # Create the plot
        fig = go.Figure()

        # Add edges
        fig.add_trace(
            go.Scatter(
                x=edge_x,
                y=edge_y,
                mode="lines",
                line=dict(width=1, color="rgba(125,125,125,0.5)"),
                hoverinfo="none",
                showlegend=False,
            )
        )

        # Add nodes
        fig.add_trace(
            go.Scatter(
                x=node_x,
                y=node_y,
                mode="markers+text",
                marker=dict(
                    size=node_sizes,
                    color=node_colors,
                    line=dict(width=2, color="white"),
                    opacity=0.8,
                ),
                text=[
                    name.split()[-1] if len(name.split()) > 2 else name
                    for name in node_names
                ],
                textposition="middle center",
                textfont=dict(size=8, color="white"),
                hovertext=node_text,
                hoverinfo="text",
                showlegend=False,
            )
        )

        # Update layout
        fig.update_layout(
            title=f"Alberta Government Knowledge Graph - {len(node_names)} entities",
            showlegend=False,
            hovermode="closest",
            margin=dict(b=20, l=5, r=5, t=40),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            height=700,
        )

        return fig

    def create_entity_type_distribution(self) -> go.Figure:
        """Create a pie chart of entity type distribution"""
        type_col = "e.type" if "e.type" in self.entities_df.columns else "type"
        type_counts = self.entities_df[type_col].value_counts()

        fig = go.Figure(
            data=[go.Pie(labels=type_counts.index, values=type_counts.values, hole=0.3)]
        )

        fig.update_layout(title="Distribution of Entity Types")
        return fig

    def create_ministry_analysis(self) -> go.Figure:
        """Create a bar chart of entities by ministry"""
        ministry_col = (
            "e.ministry" if "e.ministry" in self.entities_df.columns else "ministry"
        )
        entity_counts = self.entities_df[ministry_col].value_counts()

        fig = go.Figure(
            data=[
                go.Bar(
                    x=entity_counts.index,
                    y=entity_counts.values,
                    marker_color="#4ECDC4",
                )
            ]
        )

        fig.update_layout(
            title="Entities by Ministry",
            xaxis_title="Ministry",
            yaxis_title="Count",
            xaxis_tickangle=-45,
        )

        return fig

    def query_entity_connections(self, entity_name: str) -> pd.DataFrame:
        """Get all connections for a specific entity"""
        if self.relationships_df is None:
            return pd.DataFrame()

        connections = []

        # Find as source
        source_rels = self.relationships_df[
            self.relationships_df["source"] == entity_name
        ]
        for _, row in source_rels.iterrows():
            connections.append(
                {
                    "connected_entity": row["target"],
                    "relationship": row["relation"],
                    "direction": "outgoing",
                    "source_document": row["source_document"],
                }
            )

        # Find as target
        target_rels = self.relationships_df[
            self.relationships_df["target"] == entity_name
        ]
        for _, row in target_rels.iterrows():
            connections.append(
                {
                    "connected_entity": row["source"],
                    "relationship": row["relation"],
                    "direction": "incoming",
                    "source_document": row["source_document"],
                }
            )

        return pd.DataFrame(connections)


def main():
    """Test the visualizer"""
    viz = KnowledgeGraphVisualizer()

    # Create network graph
    network_fig = viz.create_network_graph(max_nodes=50)
    network_fig.write_html("network_graph.html")
    print("Network graph saved to network_graph.html")


if __name__ == "__main__":
    main()
