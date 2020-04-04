import math
import numpy as np
import networkx as nx
from tqdm import tqdm
import scipy.stats.mstats
import scipy.sparse as sparse
from karateclub.estimator import Estimator

class GeoScattering(Estimator):
    r"""An implementation of `"GeoScattering" <http://proceedings.mlr.press/v97/gao19e.html>`_
    from the ICML '19 paper "Geometric Scattering for Graph Data Analysis".

    Args:
        order (int): Adjacency matrix powers. Default is 4.
    """
    def __init__(self, order=4, moments=4):
        self.order = order
        self.moments = moments


    def _create_D_inverse(self, graph):
        """
        Creating a sparse inverse degree matrix.

        Arg types:
            * **graph** *(NetworkX graph)* - The graph to be embedded.

        Return types:
            * **D_inverse** *(Scipy array)* - Diagonal inverse degree matrix.
        """
        index = np.arange(graph.number_of_nodes())
        values = np.array([1.0/graph.degree[node] for node in range(graph.number_of_nodes())])
        shape = (graph.number_of_nodes(), graph.number_of_nodes())
        D_inverse = sparse.coo_matrix((values, (index, index)), shape=shape)
        return D_inverse

    def _get_normalized_adjacency(self, graph):
        """
        Calculating the normalized adjacency matrix.

        Arg types:
            * **graph** *(NetworkX graph)* - The graph of interest.

        Return types:
            * **A_hat** *(SciPy array)* - The scattering matrix of the graph.
        """
        A = nx.adjacency_matrix(graph, nodelist=range(graph.number_of_nodes()))
        D_inverse = self._create_D_inverse(graph)
        A_hat = sparse.identity(graph.number_of_nodes()) + D_inverse.dot(A)
        A_hat = 0.5*A_hat
        return A_hat

    def _calculate_wavelets(self, A_hat):
        Psi = [A_hat.power(2**power) - A_hat.power(2**(power+1)) for power in range(self.order+1)]
        return Psi

    def _create_node_feature_matrix(self, graph):
        log_degree = np.array([math.log(graph.degree(node)+1) for node in range(graph.number_of_nodes())]).reshape(-1,1)
        eccentricity = np.array([nx.eccentricity(graph,node) for node in range(graph.number_of_nodes())]).reshape(-1,1)
        clustering_coefficient = np.array([nx.clustering(graph,node) for node in range(graph.number_of_nodes())]).reshape(-1,1)
        X = np.concatenate([log_degree, eccentricity, clustering_coefficient],axis=1)
        return X

    def _get_zero_order_features(self, X):
         features = []
         X = np.abs(X)
         for col in range(X.shape[1]):
             x = np.abs(X[:, col])
             for power in range(1,self.order+1):
                 features.append(np.sum(np.power(x,power)))
         features = np.array(features).reshape(1, -1)
         return features

    def _get_first_order_features(self, Psi, X):
        features = []
        X = np.abs(X)
        for col in range(X.shape[1]):
            x = np.abs(X[:, col])
            for psi in Psi:
                filtered_x = psi.dot(x)
                for q in range(1,self.moments):
                    features.append(np.sum(np.power(np.abs(filtered_x),q)))
        features = np.array(features).reshape(1, -1) 
        return features  

    def _get_second_order_features(self, Psi, X):
        features = []
        X = np.abs(X)
        for col in range(X.shape[1]):
            x = np.abs(X[:, col])
            for i in range(self.order-1):
                for j in range(i+1, self.order):
                    psi_j = Psi[i]
                    psi_j_prime = Psi[j]                 
                    filtered_x = np.abs(psi_j_prime.dot(np.abs(psi_j.dot(x))))
                    for q in range(1,self.moments):
                       features.append(np.sum(np.power(np.abs(filtered_x),q)))

        features = np.array(features).reshape(1,-1)
        return features   
            

    def _calculate_geoscattering(self, graph):
        """
        Calculating the features of a graph.

        Arg types:
            * **graph** *(NetworkX graph)* - A graph to be embedded.

        Return types:
            * **features** *(Numpy array)* - The embedding of a single graph.
        """
        A_hat = self._get_normalized_adjacency(graph)
        Psi = self._calculate_wavelets(A_hat)
        X = self._create_node_feature_matrix(graph)
        zero_order_features = self._get_zero_order_features(X)
        first_order_features = self._get_first_order_features(Psi, X)
        second_order_features = self._get_second_order_features(Psi, X)
        features = np.concatenate([zero_order_features, first_order_features, second_order_features], axis=1)
        print(features.shape)
        return features

    def fit(self, graphs):
        """
        Fitting a NetLSD model.

        Arg types:
            * **graphs** *(List of NetworkX graphs)* - The graphs to be embedded.
        """
        self._check_graphs(graphs)
        self._embedding = [self._calculate_geoscattering(graph) for graph in tqdm(graphs)]


    def get_embedding(self):
        r"""Getting the embedding of graphs.

        Return types:
            * **embedding** *(Numpy array)* - The embedding of graphs.
        """
        return np.array(self._embedding)
