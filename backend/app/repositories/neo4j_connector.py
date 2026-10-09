"""Small original connection adapter; all secrets come from the environment."""
import os
from neo4j import GraphDatabase


class GraphConnection:
    def __init__(self):
        self.driver = GraphDatabase.driver(os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
                                         auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "")),
                                         connection_timeout=5)


neo4j_connector = GraphConnection()
