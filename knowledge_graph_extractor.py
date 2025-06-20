#!/usr/bin/env python3
"""
Knowledge Graph Extractor for Alberta Government Documents
Uses Databricks Connect + Llama 70B + Kuzu for entity and relationship extraction
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Any
import pandas as pd
import kuzu
import re
from dataclasses import dataclass
from databricks import sql
from databricks.connect import DatabricksSession
import yaml

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Entity:
    """Represents an extracted entity"""

    name: str
    type: str
    description: str
    source_document: str
    ministry: str
    confidence: float = 0.0


@dataclass
class Relationship:
    """Represents a relationship between entities"""

    source_entity: str
    relation_type: str
    target_entity: str
    description: str
    source_document: str
    confidence: float = 0.0


class KnowledgeGraphExtractor:
    """Main class for extracting knowledge graphs from government documents"""

    def __init__(self, databricks_config_path: str = "databricks.yml"):
        self.databricks_config = self._load_databricks_config(databricks_config_path)
        self.spark = None
        self.kuzu_db = None
        self.initialize_databases()

    def _load_databricks_config(self, config_path: str) -> Dict:
        """Load Databricks configuration from YAML file"""
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        return config

    def initialize_databases(self):
        """Initialize Databricks connection and Kuzu database"""
        try:
            # Initialize Databricks connection
            logger.info("Initializing Databricks connection...")
            self.spark = DatabricksSession.builder.getOrCreate()
            logger.info("Databricks connection established")

            # Initialize Kuzu database
            logger.info("Initializing Kuzu database...")
            db_path = "alberta_knowledge_graph.db"
            if os.path.exists(db_path):
                os.remove(db_path)  # Start fresh
            self.kuzu_db = kuzu.Database(db_path)
            self.kuzu_conn = kuzu.Connection(self.kuzu_db)
            self._create_kuzu_schema()
            logger.info(f"Kuzu database initialized at {db_path}")

        except Exception as e:
            logger.error(f"Failed to initialize databases: {e}")
            raise

    def _create_kuzu_schema(self):
        """Create the knowledge graph schema in Kuzu"""
        # Create Entity node table
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

        # Create Relationship edge table
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

    def extract_entities_and_relationships_with_llama(
        self, text: str, source_doc: str, ministry: str
    ) -> Tuple[List[Entity], List[Relationship]]:
        """Use Llama 70B via Databricks to extract entities and relationships"""

        # Enhanced prompt for GraphRAG-style extraction
        prompt = f"""
You are an expert in knowledge graph extraction for government documents. 
Extract meaningful entities and relationships from this Alberta government document.

Focus on:
- Government programs, policies, and initiatives
- Key officials, ministers, and departments
- Budget items, funding amounts, and financial programs
- Laws, regulations, and legal frameworks  
- Services provided to citizens
- Dates and deadlines for important events
- Organizations and institutions
- Geographic locations (cities, regions, facilities)

Avoid extracting:
- Common navigation elements
- Generic web content
- Dates without context
- Simple dollar amounts without purpose

Document Ministry: {ministry}
Document Source: {source_doc}

Text to analyze:
{text[:4000]}  # Limit to first 4000 chars to avoid token limits

Return your response as valid JSON with this exact structure:
{{
  "entities": [
    {{
      "name": "entity_name",
      "type": "PROGRAM|POLICY|PERSON|ORGANIZATION|LOCATION|BUDGET_ITEM|SERVICE|LAW|EVENT",
      "description": "brief description of what this entity represents",
      "confidence": 0.8
    }}
  ],
  "relationships": [
    {{
      "source_entity": "entity1_name",
      "relation_type": "MANAGES|FUNDS|IMPLEMENTS|LOCATED_IN|PART_OF|PROVIDES|REGULATES|COLLABORATES_WITH",
      "target_entity": "entity2_name", 
      "description": "description of the relationship",
      "confidence": 0.9
    }}
  ]
}}

Only return the JSON, no other text.
"""

        try:
            # Use Databricks SQL to call Llama model
            sql_query = f"""
            SELECT ai_query(
                'databricks-llama-2-70b-chat',
                '{prompt.replace("'", "''")}'  -- Escape single quotes
            ) as response
            """

            result = self.spark.sql(sql_query).collect()
            response_text = result[0]["response"]

            # Parse the JSON response
            try:
                response_json = json.loads(response_text)
            except json.JSONDecodeError:
                # Try to extract JSON from response if it's wrapped in other text
                import re

                json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
                if json_match:
                    response_json = json.loads(json_match.group())
                else:
                    logger.warning(
                        f"Failed to parse LLM response as JSON: {response_text}"
                    )
                    return [], []

            # Convert to Entity and Relationship objects
            entities = []
            for ent in response_json.get("entities", []):
                entities.append(
                    Entity(
                        name=ent["name"],
                        type=ent["type"],
                        description=ent["description"],
                        source_document=source_doc,
                        ministry=ministry,
                        confidence=ent.get("confidence", 0.7),
                    )
                )

            relationships = []
            for rel in response_json.get("relationships", []):
                relationships.append(
                    Relationship(
                        source_entity=rel["source_entity"],
                        relation_type=rel["relation_type"],
                        target_entity=rel["target_entity"],
                        description=rel["description"],
                        source_document=source_doc,
                        confidence=rel.get("confidence", 0.7),
                    )
                )

            return entities, relationships

        except Exception as e:
            logger.error(f"Error calling Llama model: {e}")
            return [], []

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
                    content = parts[2]  # Main content after frontmatter
                else:
                    ministry = file_path.parent.name.replace("_", " ")
                    source_url = str(file_path)
            else:
                ministry = file_path.parent.name.replace("_", " ")
                source_url = str(file_path)

            # Clean the content - remove excessive whitespace and navigation elements
            content = re.sub(r"\n+", "\n", content)
            content = re.sub(
                r"^\s*Skip to content\s*$", "", content, flags=re.MULTILINE
            )
            content = re.sub(
                r"^\s*\[.*?\]\s*$", "", content, flags=re.MULTILINE
            )  # Remove standalone links

            # Split into chunks if document is very long
            max_chunk_size = 3000
            if len(content) > max_chunk_size:
                # Split by paragraphs and combine into chunks
                paragraphs = content.split("\n\n")
                chunks = []
                current_chunk = ""

                for para in paragraphs:
                    if len(current_chunk) + len(para) > max_chunk_size:
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = para
                    else:
                        current_chunk += "\n\n" + para if current_chunk else para

                if current_chunk:
                    chunks.append(current_chunk)
            else:
                chunks = [content]

            all_entities = []
            all_relationships = []

            # Process each chunk
            for i, chunk in enumerate(chunks):
                if len(chunk.strip()) < 100:  # Skip very short chunks
                    continue

                source_doc = (
                    f"{source_url}#chunk_{i}" if len(chunks) > 1 else source_url
                )
                entities, relationships = (
                    self.extract_entities_and_relationships_with_llama(
                        chunk, source_doc, ministry
                    )
                )
                all_entities.extend(entities)
                all_relationships.extend(relationships)

            return all_entities, all_relationships

        except Exception as e:
            logger.error(f"Error processing document {file_path}: {e}")
            return [], []

    def store_in_kuzu(self, entities: List[Entity], relationships: List[Relationship]):
        """Store entities and relationships in Kuzu database"""

        # Insert entities (using MERGE to handle duplicates)
        for entity in entities:
            try:
                self.kuzu_conn.execute(
                    f"""
                    MERGE (e:Entity {{name: '{entity.name.replace("'", "''")}'}})
                    ON CREATE SET e.type = '{entity.type}',
                                  e.description = '{entity.description.replace("'", "''")}',
                                  e.source_document = '{entity.source_document}',
                                  e.ministry = '{entity.ministry}',
                                  e.confidence = {entity.confidence}
                    ON MATCH SET e.confidence = CASE WHEN {entity.confidence} > e.confidence 
                                                    THEN {entity.confidence} 
                                                    ELSE e.confidence END
                """
                )
            except Exception as e:
                logger.warning(f"Failed to insert entity {entity.name}: {e}")

        # Insert relationships
        for rel in relationships:
            try:
                self.kuzu_conn.execute(
                    f"""
                    MATCH (a:Entity {{name: '{rel.source_entity.replace("'", "''")}'}}),
                          (b:Entity {{name: '{rel.target_entity.replace("'", "''")}'}})
                    CREATE (a)-[r:Relationship {{
                        relation_type: '{rel.relation_type}',
                        description: '{rel.description.replace("'", "''")}',
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
        self, markdown_dir: str, max_documents: int = 10, max_triplets: int = 100
    ):
        """Extract knowledge graph from directory of markdown files"""
        markdown_path = Path(markdown_dir)

        if not markdown_path.exists():
            logger.error(f"Directory not found: {markdown_dir}")
            return

        # Get all markdown files
        md_files = list(markdown_path.rglob("*.md"))
        logger.info(f"Found {len(md_files)} markdown files")

        # Limit number of documents to process
        if len(md_files) > max_documents:
            md_files = md_files[:max_documents]
            logger.info(f"Processing first {max_documents} documents")

        all_entities = []
        all_relationships = []
        triplet_count = 0

        for md_file in md_files:
            if triplet_count >= max_triplets:
                logger.info(f"Reached maximum triplets limit: {max_triplets}")
                break

            entities, relationships = self.process_document(md_file)

            if entities or relationships:
                all_entities.extend(entities)
                all_relationships.extend(relationships)
                triplet_count += len(relationships)

                # Store in database incrementally
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

        # Export triplets for easy consumption
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
        print("\n=== SAMPLE KNOWLEDGE GRAPH TRIPLETS ===")
        for i, row in triplets_df.head(20).iterrows():
            print(f"{row['triplet']} (confidence: {row['confidence']:.2f})")

    def close(self):
        """Clean up database connections"""
        if self.kuzu_conn:
            self.kuzu_conn.close()
        if self.spark:
            self.spark.stop()


def main():
    """Main execution function"""
    extractor = KnowledgeGraphExtractor()

    try:
        # Extract from the Alberta documents
        markdown_dir = "alberta_pdf_catalog_20250617_224203/markdown_content"
        extractor.extract_from_directory(
            markdown_dir=markdown_dir,
            max_documents=5,  # Start with 5 documents
            max_triplets=100,  # Target 100 triplets as requested
        )

        # Export results
        extractor.export_results()

    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        raise
    finally:
        extractor.close()


if __name__ == "__main__":
    main()
