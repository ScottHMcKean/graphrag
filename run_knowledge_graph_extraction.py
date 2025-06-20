#!/usr/bin/env python3
"""
Simplified Knowledge Graph Extraction Runner
Handles authentication and provides fallback for local execution
"""

import os
import sys
import logging
from pathlib import Path
import json
import re
from typing import List, Dict, Tuple
import pandas as pd
import kuzu
import yaml
from dataclasses import dataclass

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class Entity:
    name: str
    type: str
    description: str
    source_document: str
    ministry: str
    confidence: float = 0.0


@dataclass
class Relationship:
    source_entity: str
    relation_type: str
    target_entity: str
    description: str
    source_document: str
    confidence: float = 0.0


class SimpleKnowledgeExtractor:
    """Simplified knowledge graph extractor with rule-based extraction"""

    def __init__(self):
        self.kuzu_db = None
        self.kuzu_conn = None
        self.initialize_kuzu()

    def initialize_kuzu(self):
        """Initialize Kuzu database"""
        logger.info("Initializing Kuzu database...")
        db_path = "alberta_knowledge_graph.db"
        if os.path.exists(db_path):
            os.remove(db_path)
        self.kuzu_db = kuzu.Database(db_path)
        self.kuzu_conn = kuzu.Connection(self.kuzu_db)
        self._create_kuzu_schema()
        logger.info(f"Kuzu database initialized at {db_path}")

    def _create_kuzu_schema(self):
        """Create the knowledge graph schema in Kuzu"""
        self.kuzu_conn.execute(
            """
            CREATE NODE TABLE Entity(
                name STRING,
                type STRING,
                description STRING,
                source_document STRING,
                ministry STRING,
                confidence DOUBLE,
                PRIMARY KEY (name)
            )
        """
        )

        self.kuzu_conn.execute(
            """
            CREATE REL TABLE Relationship(
                FROM Entity TO Entity,
                relation_type STRING,
                description STRING,
                source_document STRING,
                confidence DOUBLE
            )
        """
        )

        logger.info("Kuzu schema created successfully")

    def extract_entities_simple(
        self, text: str, source_doc: str, ministry: str
    ) -> Tuple[List[Entity], List[Relationship]]:
        """Extract entities and relationships using rule-based approach"""
        entities = []
        relationships = []

        # Entity extraction patterns
        patterns = {
            "PROGRAM": [
                r"([A-Z][a-z]+ [A-Z][a-z]+ Program)",
                r"([A-Z][a-z]+ Program)",
                r"(Community Adult Learning Program)",
                r"(Child Care Subsidy Program)",
                r"(Foster and Kinship Care)",
            ],
            "ORGANIZATION": [
                r"(Government of Alberta)",
                r"(Ministry of [A-Z][a-z ]+)",
                r"(Department of [A-Z][a-z ]+)",
                r"(Alberta [A-Z][a-z ]+)",
            ],
            "POLICY": [
                r"([A-Z][a-z]+ Act)",
                r"([A-Z][a-z]+ Policy)",
                r"([A-Z][a-z]+ Strategy)",
                r"([A-Z][a-z]+ Plan)",
            ],
            "SERVICE": [
                r"(vehicle registration)",
                r"(elder abuse)",
                r"(child care)",
                r"(education services)",
            ],
            "BUDGET_ITEM": [
                r"Budget (\d{4})",
                r"(\$[\d,]+ million)",
                r"(\$[\d,]+)",
            ],
            "LOCATION": [
                r"(Alberta)",
                r"(Edmonton)",
                r"(Calgary)",
            ],
        }

        # Extract entities
        found_entities = set()
        for entity_type, type_patterns in patterns.items():
            for pattern in type_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0]
                    if len(match.strip()) > 2 and match not in found_entities:
                        entities.append(
                            Entity(
                                name=match.strip(),
                                type=entity_type,
                                description=f"{entity_type} mentioned in {ministry} documents",
                                source_document=source_doc,
                                ministry=ministry,
                                confidence=0.8,
                            )
                        )
                        found_entities.add(match)

        # Extract relationships (simplified)
        entity_names = [e.name for e in entities]

        # Simple relationship patterns
        for i, entity1 in enumerate(entity_names):
            for j, entity2 in enumerate(entity_names):
                if i != j:
                    # Look for mentions of both entities near each other
                    entity1_pos = text.lower().find(entity1.lower())
                    entity2_pos = text.lower().find(entity2.lower())

                    if (
                        entity1_pos != -1
                        and entity2_pos != -1
                        and abs(entity1_pos - entity2_pos) < 500
                    ):
                        # Determine relationship type based on entity types
                        e1_type = entities[i].type
                        e2_type = entities[j].type

                        relation_type = "RELATED_TO"  # Default
                        if e1_type == "ORGANIZATION" and e2_type == "PROGRAM":
                            relation_type = "MANAGES"
                        elif e1_type == "ORGANIZATION" and e2_type == "SERVICE":
                            relation_type = "PROVIDES"
                        elif e1_type == "PROGRAM" and e2_type == "BUDGET_ITEM":
                            relation_type = "FUNDED_BY"
                        elif e1_type == "ORGANIZATION" and e2_type == "LOCATION":
                            relation_type = "LOCATED_IN"

                        relationships.append(
                            Relationship(
                                source_entity=entity1,
                                relation_type=relation_type,
                                target_entity=entity2,
                                description=f"{entity1} {relation_type.lower().replace('_', ' ')} {entity2}",
                                source_document=source_doc,
                                confidence=0.7,
                            )
                        )

        return entities, relationships

    def process_document(
        self, file_path: Path
    ) -> Tuple[List[Entity], List[Relationship]]:
        """Process a single markdown document"""
        logger.info(f"Processing document: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract metadata from frontmatter
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1])
                    ministry = frontmatter.get("ministry", "Unknown")
                    source_url = frontmatter.get("url", str(file_path))
                    content = parts[2]
                else:
                    ministry = file_path.parent.name.replace("_", " ")
                    source_url = str(file_path)
            else:
                ministry = file_path.parent.name.replace("_", " ")
                source_url = str(file_path)

            # Clean content
            content = re.sub(r"\n+", "\n", content)
            content = re.sub(
                r"^\s*Skip to content\s*$", "", content, flags=re.MULTILINE
            )
            content = re.sub(r"^\s*\[.*?\]\s*$", "", content, flags=re.MULTILINE)

            # Extract entities and relationships
            entities, relationships = self.extract_entities_simple(
                content, source_url, ministry
            )

            return entities, relationships

        except Exception as e:
            logger.error(f"Error processing document {file_path}: {e}")
            return [], []

    def store_in_kuzu(self, entities: List[Entity], relationships: List[Relationship]):
        """Store entities and relationships in Kuzu database"""

        # Insert entities
        for entity in entities:
            try:
                # Clean entity name for safe SQL
                clean_name = entity.name.replace("'", "''")
                clean_desc = entity.description.replace("'", "''")
                clean_ministry = entity.ministry.replace("'", "''")

                self.kuzu_conn.execute(
                    f"""
                    CREATE (e:Entity {{
                        name: '{clean_name}',
                        type: '{entity.type}',
                        description: '{clean_desc}',
                        source_document: '{entity.source_document}',
                        ministry: '{clean_ministry}',
                        confidence: {entity.confidence}
                    }})
                """
                )
            except Exception as e:
                logger.warning(f"Failed to insert entity {entity.name}: {e}")

        # Insert relationships
        for rel in relationships:
            try:
                clean_source = rel.source_entity.replace("'", "''")
                clean_target = rel.target_entity.replace("'", "''")
                clean_desc = rel.description.replace("'", "''")

                self.kuzu_conn.execute(
                    f"""
                    MATCH (a:Entity {{name: '{clean_source}'}}),
                          (b:Entity {{name: '{clean_target}'}})
                    CREATE (a)-[r:Relationship {{
                        relation_type: '{rel.relation_type}',
                        description: '{clean_desc}',
                        source_document: '{rel.source_document}',
                        confidence: {rel.confidence}
                    }}]->(b)
                """
                )
            except Exception as e:
                logger.warning(
                    f"Failed to insert relationship {rel.source_entity} -> {rel.target_entity}: {e}"
                )

    def extract_from_directory(
        self, markdown_dir: str, max_documents: int = 5, max_triplets: int = 100
    ):
        """Extract knowledge graph from directory of markdown files"""
        markdown_path = Path(markdown_dir)

        if not markdown_path.exists():
            logger.error(f"Directory not found: {markdown_dir}")
            return

        # Get all markdown files
        md_files = list(markdown_path.rglob("*.md"))
        logger.info(f"Found {len(md_files)} markdown files")

        # Prioritize certain document types
        priority_docs = []
        other_docs = []

        for md_file in md_files:
            if any(
                keyword in md_file.name.lower()
                for keyword in ["budget", "program", "policy", "service"]
            ):
                priority_docs.append(md_file)
            else:
                other_docs.append(md_file)

        # Process priority docs first
        selected_files = (priority_docs + other_docs)[:max_documents]
        logger.info(f"Processing {len(selected_files)} documents")

        all_entities = []
        all_relationships = []
        triplet_count = 0

        for md_file in selected_files:
            if triplet_count >= max_triplets:
                logger.info(f"Reached maximum triplets limit: {max_triplets}")
                break

            entities, relationships = self.process_document(md_file)

            if entities or relationships:
                all_entities.extend(entities)
                all_relationships.extend(relationships)
                triplet_count += len(relationships)

                # Store in database
                self.store_in_kuzu(entities, relationships)

                logger.info(
                    f"Processed {md_file.name}: {len(entities)} entities, {len(relationships)} relationships"
                )

        logger.info(
            f"Total extracted: {len(all_entities)} entities, {len(all_relationships)} relationships"
        )
        return all_entities, all_relationships

    def export_results(self, output_dir: str = "knowledge_graph_output"):
        """Export the knowledge graph results"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        try:
            # Export entities
            entities_result = self.kuzu_conn.execute("MATCH (e:Entity) RETURN e.*")
            entities_df = entities_result.get_as_df()
            entities_df.to_csv(output_path / "entities.csv", index=False)

            # Export relationships
            rels_result = self.kuzu_conn.execute(
                """
                MATCH (a:Entity)-[r:Relationship]->(b:Entity) 
                RETURN a.name as source_entity, r.relation_type, b.name as target_entity,
                       r.description, r.source_document, r.confidence
            """
            )
            rels_df = rels_result.get_as_df()
            rels_df.to_csv(output_path / "relationships.csv", index=False)

            # Export triplets
            triplets_result = self.kuzu_conn.execute(
                """
                MATCH (a:Entity)-[r:Relationship]->(b:Entity) 
                RETURN a.name + ' | ' + r.relation_type + ' | ' + b.name as triplet,
                       r.confidence, r.source_document
                ORDER BY r.confidence DESC
            """
            )
            triplets_df = triplets_result.get_as_df()
            triplets_df.to_csv(output_path / "triplets.csv", index=False)

            logger.info(f"Results exported to {output_path}")

            # Print sample results
            print("\n" + "=" * 50)
            print("SAMPLE KNOWLEDGE GRAPH TRIPLETS")
            print("=" * 50)

            for i, row in triplets_df.head(20).iterrows():
                print(f"{row['triplet']} (confidence: {row['confidence']:.2f})")

            print(f"\nTotal: {len(entities_df)} entities, {len(rels_df)} relationships")
            print(f"Files saved to: {output_path.absolute()}")

        except Exception as e:
            logger.error(f"Error exporting results: {e}")

    def close(self):
        """Clean up database connections"""
        if self.kuzu_conn:
            self.kuzu_conn.close()


def main():
    """Main execution function"""
    logger.info("Starting Alberta Government Knowledge Graph Extraction")

    extractor = SimpleKnowledgeExtractor()

    try:
        # Extract from the Alberta documents
        markdown_dir = "alberta_pdf_catalog_20250617_224203/markdown_content"

        if not Path(markdown_dir).exists():
            logger.error(f"Markdown directory not found: {markdown_dir}")
            return

        extractor.extract_from_directory(
            markdown_dir=markdown_dir,
            max_documents=1000,  # Process all available documents
            max_triplets=10000,  # Allow for many more triplets
        )

        # Export results
        extractor.export_results()

        logger.info("Knowledge graph extraction completed successfully!")

    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        raise
    finally:
        extractor.close()


if __name__ == "__main__":
    main()
