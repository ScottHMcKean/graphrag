#!/usr/bin/env python3
"""
Knowledge Graph Query Library
Predefined queries for exploring the Alberta Government Knowledge Graph
"""

import pandas as pd
import kuzu
from typing import List, Dict, Any, Optional, Tuple
import networkx as nx
from collections import Counter, defaultdict


class KnowledgeGraphQueries:
    """Library of useful queries for the Alberta Government Knowledge Graph"""

    def __init__(self, db_path: str = "alberta_knowledge_graph.db"):
        """Initialize connection to Kuzu database"""
        self.db_path = db_path
        try:
            self.db = kuzu.Database(db_path)
            self.conn = kuzu.Connection(self.db)
        except:
            self.db = None
            self.conn = None

            # Load data into DataFrames for backup queries
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
        except:
            self.entities_df = None
            self.relationships_df = None

    def find_policy_programs(self) -> pd.DataFrame:
        """Find all policy-related programs and their connections"""
        try:
            query = """
            MATCH (policy:Entity {type: 'Policy'})-[r:RELATES_TO]-(program:Entity {type: 'Program'})
            RETURN policy.name as policy_name, program.name as program_name, 
                   r.relation_type as relationship, policy.ministry as ministry
            ORDER BY policy.ministry, policy.name
            """
            result = self.conn.execute(query)
            return result.get_as_df()
        except:
            # Fallback using DataFrames
            if self.entities_df is None or self.relationships_df is None:
                return pd.DataFrame()

            type_col = "e.type" if "e.type" in self.entities_df.columns else "type"
            policies = self.entities_df[self.entities_df[type_col] == "POLICY"]
            programs = self.entities_df[self.entities_df[type_col] == "PROGRAM"]

            results = []
            for _, rel in self.relationships_df.iterrows():
                if (
                    rel["source"] in policies["name"].values
                    and rel["target"] in programs["name"].values
                ):
                    policy_ministry = policies[policies["name"] == rel["source"]][
                        "ministry"
                    ].iloc[0]
                    results.append(
                        {
                            "policy_name": rel["source"],
                            "program_name": rel["target"],
                            "relationship": rel["relation"],
                            "ministry": policy_ministry,
                        }
                    )
                elif (
                    rel["target"] in policies["name"].values
                    and rel["source"] in programs["name"].values
                ):
                    policy_ministry = policies[policies["name"] == rel["target"]][
                        "ministry"
                    ].iloc[0]
                    results.append(
                        {
                            "policy_name": rel["target"],
                            "program_name": rel["source"],
                            "relationship": rel["relation"],
                            "ministry": policy_ministry,
                        }
                    )

            return pd.DataFrame(results)

    def find_cross_ministry_connections(self) -> pd.DataFrame:
        """Find entities that span multiple ministries"""
        if self.relationships_df is None or self.entities_df is None:
            return pd.DataFrame()

        # Create entity-ministry mapping
        entity_ministry = dict(
            zip(self.entities_df["name"], self.entities_df["ministry"])
        )

        cross_ministry_rels = []
        for _, rel in self.relationships_df.iterrows():
            source_ministry = entity_ministry.get(rel["source"])
            target_ministry = entity_ministry.get(rel["target"])

            if (
                source_ministry
                and target_ministry
                and source_ministry != target_ministry
            ):
                cross_ministry_rels.append(
                    {
                        "entity_1": rel["source"],
                        "ministry_1": source_ministry,
                        "relationship": rel["relation"],
                        "entity_2": rel["target"],
                        "ministry_2": target_ministry,
                        "source_document": rel["source_document"],
                    }
                )

        return pd.DataFrame(cross_ministry_rels)

    def find_budget_related_entities(self) -> pd.DataFrame:
        """Find all entities related to budget and funding"""
        if self.entities_df is None:
            return pd.DataFrame()

        budget_keywords = [
            "budget",
            "funding",
            "financial",
            "cost",
            "expenditure",
            "revenue",
        ]

        budget_entities = self.entities_df[
            (self.entities_df["type"] == "Budget")
            | (
                self.entities_df["name"].str.contains(
                    "|".join(budget_keywords), case=False, na=False
                )
            )
            | (
                self.entities_df["description"].str.contains(
                    "|".join(budget_keywords), case=False, na=False
                )
            )
        ]

        return budget_entities[["name", "type", "ministry", "description"]].rename(
            columns={"name": "entity_name", "type": "entity_type"}
        )

    def find_legislative_framework(self) -> pd.DataFrame:
        """Find legislative acts and their related entities"""
        if self.entities_df is None or self.relationships_df is None:
            return pd.DataFrame()

        # Find legislation entities
        legislation = self.entities_df[
            (self.entities_df["type"] == "Legislation")
            | (
                self.entities_df["name"].str.contains(
                    "Act|Bill|Law|Regulation", case=False, na=False
                )
            )
        ]

        # Find their connections
        legislative_connections = []
        for _, leg in legislation.iterrows():
            connections = self.relationships_df[
                (self.relationships_df["source"] == leg["name"])
                | (self.relationships_df["target"] == leg["name"])
            ]

            for _, conn in connections.iterrows():
                other_entity = (
                    conn["target"] if conn["source"] == leg["name"] else conn["source"]
                )
                other_info = self.entities_df[self.entities_df["name"] == other_entity]
                other_type = (
                    other_info["type"].iloc[0] if not other_info.empty else "Unknown"
                )

                legislative_connections.append(
                    {
                        "legislation": leg["name"],
                        "connected_entity": other_entity,
                        "entity_type": other_type,
                        "relationship": conn["relation"],
                        "ministry": leg["ministry"],
                    }
                )

        return pd.DataFrame(legislative_connections)

    def find_program_hierarchies(self) -> pd.DataFrame:
        """Find program hierarchies and sub-programs"""
        if self.entities_df is None or self.relationships_df is None:
            return pd.DataFrame()

        programs = self.entities_df[self.entities_df["type"] == "Program"]

        hierarchies = []
        for _, rel in self.relationships_df.iterrows():
            if (
                rel["source"] in programs["name"].values
                and rel["target"] in programs["name"].values
                and rel["relation"] in ["manages", "oversees", "contains", "includes"]
            ):

                parent_info = programs[programs["name"] == rel["source"]].iloc[0]
                child_info = programs[programs["name"] == rel["target"]].iloc[0]

                hierarchies.append(
                    {
                        "parent_program": rel["source"],
                        "child_program": rel["target"],
                        "relationship": rel["relation"],
                        "ministry": parent_info["ministry"],
                        "parent_description": parent_info["description"],
                        "child_description": child_info["description"],
                    }
                )

        return pd.DataFrame(hierarchies)

    def find_entity_clusters(self, min_cluster_size: int = 3) -> Dict[str, List[str]]:
        """Find clusters of highly connected entities"""
        if self.relationships_df is None:
            return {}

        # Create NetworkX graph
        G = nx.from_pandas_edgelist(
            self.relationships_df, source="source", target="target"
        )

        # Find communities using greedy modularity
        try:
            import networkx.algorithms.community as nx_comm

            communities = nx_comm.greedy_modularity_communities(G)

            clusters = {}
            for i, community in enumerate(communities):
                if len(community) >= min_cluster_size:
                    clusters[f"Cluster_{i+1}"] = list(community)

            return clusters
        except:
            # Simple fallback: find connected components
            components = list(nx.connected_components(G))
            clusters = {}
            for i, component in enumerate(components):
                if len(component) >= min_cluster_size:
                    clusters[f"Component_{i+1}"] = list(component)

            return clusters

    def find_ministry_overlaps(self) -> pd.DataFrame:
        """Find entities mentioned in multiple ministry documents"""
        if self.entities_df is None:
            return pd.DataFrame()

        # Group by entity name and count unique ministries
        entity_ministries = (
            self.entities_df.groupby("name")["ministry"].nunique().reset_index()
        )
        entity_ministries.columns = ["entity_name", "ministry_count"]

        # Find entities appearing in multiple ministries
        overlapping_entities = entity_ministries[
            entity_ministries["ministry_count"] > 1
        ]

        # Get details for overlapping entities
        overlap_details = []
        for _, entity in overlapping_entities.iterrows():
            entity_instances = self.entities_df[
                self.entities_df["name"] == entity["entity_name"]
            ]
            ministries = entity_instances["ministry"].unique()
            entity_type = entity_instances["type"].iloc[0]

            overlap_details.append(
                {
                    "entity_name": entity["entity_name"],
                    "entity_type": entity_type,
                    "ministry_count": entity["ministry_count"],
                    "ministries": ", ".join(ministries),
                    "documents": ", ".join(
                        entity_instances["source_document"].unique()
                    ),
                }
            )

        return pd.DataFrame(overlap_details)

    def find_shortest_paths(self, entity1: str, entity2: str) -> List[str]:
        """Find shortest path between two entities"""
        if self.relationships_df is None:
            return []

        G = nx.from_pandas_edgelist(
            self.relationships_df, source="source", target="target"
        )

        try:
            path = nx.shortest_path(G, entity1, entity2)
            return path
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    def find_influential_entities(self, top_n: int = 20) -> pd.DataFrame:
        """Find most influential entities using centrality measures"""
        if self.relationships_df is None:
            return pd.DataFrame()

        G = nx.from_pandas_edgelist(
            self.relationships_df, source="source", target="target"
        )

        # Calculate centrality measures
        degree_centrality = nx.degree_centrality(G)
        betweenness_centrality = nx.betweenness_centrality(G)

        # Combine results
        influential_entities = []
        # Handle different column naming conventions
        name_col = "e.name" if "e.name" in self.entities_df.columns else "name"
        type_col = "e.type" if "e.type" in self.entities_df.columns else "type"
        ministry_col = (
            "e.ministry" if "e.ministry" in self.entities_df.columns else "ministry"
        )

        for entity in G.nodes():
            entity_info = self.entities_df[self.entities_df[name_col] == entity]
            entity_type = (
                entity_info[type_col].iloc[0] if not entity_info.empty else "Unknown"
            )
            ministry = (
                entity_info[ministry_col].iloc[0]
                if not entity_info.empty
                else "Unknown"
            )

            influential_entities.append(
                {
                    "entity": entity,
                    "type": entity_type,
                    "ministry": ministry,
                    "degree_centrality": degree_centrality.get(entity, 0),
                    "betweenness_centrality": betweenness_centrality.get(entity, 0),
                    "total_connections": G.degree(entity),
                }
            )

        df = pd.DataFrame(influential_entities)

        # Calculate combined influence score
        df["influence_score"] = (
            df["degree_centrality"] * 0.6 + df["betweenness_centrality"] * 0.4
        )

        return df.sort_values("influence_score", ascending=False).head(top_n)

    def find_relationship_patterns(self) -> pd.DataFrame:
        """Analyze patterns in relationship types"""
        if self.relationships_df is None or self.entities_df is None:
            return pd.DataFrame()

        # Create entity type mapping
        entity_types = dict(zip(self.entities_df["name"], self.entities_df["type"]))

        # Analyze relationship patterns
        patterns = []
        for _, rel in self.relationships_df.iterrows():
            source_type = entity_types.get(rel["source"], "Unknown")
            target_type = entity_types.get(rel["target"], "Unknown")

            patterns.append(
                {
                    "source_type": source_type,
                    "relationship": rel["relation"],
                    "target_type": target_type,
                    "pattern": f"{source_type} → {rel['relation']} → {target_type}",
                }
            )

        pattern_df = pd.DataFrame(patterns)
        pattern_counts = pattern_df["pattern"].value_counts().reset_index()
        pattern_counts.columns = ["pattern", "count"]

        return pattern_counts.head(20)

    def search_entities(self, search_term: str) -> pd.DataFrame:
        """Search for entities by name or description"""
        if self.entities_df is None:
            return pd.DataFrame()

        search_term = search_term.lower()

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
        source_col = (
            "e.source_document"
            if "e.source_document" in self.entities_df.columns
            else "source_document"
        )

        results = self.entities_df[
            (self.entities_df[name_col].str.lower().str.contains(search_term, na=False))
            | (
                self.entities_df[desc_col]
                .str.lower()
                .str.contains(search_term, na=False)
            )
        ]

        return results[[name_col, type_col, ministry_col, desc_col, source_col]].rename(
            columns={
                name_col: "name",
                type_col: "type",
                ministry_col: "ministry",
                desc_col: "description",
                source_col: "source_document",
            }
        )


def main():
    """Example usage of the query library"""
    queries = KnowledgeGraphQueries()

    print("=== Policy-Program Connections ===")
    policy_programs = queries.find_policy_programs()
    print(f"Found {len(policy_programs)} policy-program connections")
    print(policy_programs.head())

    print("\n=== Cross-Ministry Connections ===")
    cross_ministry = queries.find_cross_ministry_connections()
    print(f"Found {len(cross_ministry)} cross-ministry connections")
    if not cross_ministry.empty:
        print(cross_ministry.head())

    print("\n=== Budget-Related Entities ===")
    budget_entities = queries.find_budget_related_entities()
    print(f"Found {len(budget_entities)} budget-related entities")
    if not budget_entities.empty:
        print(budget_entities.head())

    print("\n=== Most Influential Entities ===")
    influential = queries.find_influential_entities(top_n=10)
    if not influential.empty:
        print(
            influential[
                ["entity", "type", "ministry", "influence_score", "total_connections"]
            ]
        )


if __name__ == "__main__":
    main()
