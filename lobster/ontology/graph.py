import networkx as nx
from .models import Library, Developer, SOQuestion, HNPost, Edge, NodeType


class OntologyGraph:
    def __init__(self):
        self.g = nx.MultiDiGraph()

    def add_library(self, lib: Library):
        self.g.add_node(lib.id, type=NodeType.LIBRARY, data=lib)

    def add_developer(self, dev: Developer):
        self.g.add_node(dev.id, type=NodeType.DEVELOPER, data=dev)

    def add_so_question(self, q: SOQuestion):
        self.g.add_node(q.id, type=NodeType.SO_QUESTION, data=q)

    def add_hn_post(self, post: HNPost):
        self.g.add_node(post.id, type=NodeType.HN_POST, data=post)

    def add_edge(self, edge: Edge):
        self.g.add_edge(
            edge.source_id,
            edge.target_id,
            type=edge.edge_type,
            weight=edge.weight,
            **edge.metadata,
        )

    def get_node(self, node_id: str):
        return self.g.nodes.get(node_id)

    def neighbors_of_type(self, node_id: str, node_type: NodeType):
        return [
            n for n in self.g.successors(node_id)
            if self.g.nodes[n].get("type") == node_type
        ]

    def stats(self):
        return {
            "nodes": self.g.number_of_nodes(),
            "edges": self.g.number_of_edges(),
        }
