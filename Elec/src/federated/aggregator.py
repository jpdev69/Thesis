"""Enhanced federated learning aggregation with FedProx, privacy, and convergence monitoring"""

import numpy as np
from typing import List, Optional, Dict


class FederatedAggregator:
    """Federated learning aggregator with multiple strategies including
    FedAvg, FedProx, quality-weighted aggregation, and differential privacy."""
    
    def __init__(self, aggregation_method='fedavg', proximal_mu=0.01, 
                 dp_epsilon=1.0, dp_delta=1e-5, convergence_threshold=1e-4):
        """
        Args:
            aggregation_method: 'fedavg', 'fedprox', or 'quality_weighted'
            proximal_mu: Proximal term strength for FedProx
            dp_epsilon: Differential privacy epsilon parameter
            dp_delta: Differential privacy delta parameter
            convergence_threshold: Threshold for convergence detection
        """
        self.aggregation_method = aggregation_method
        self.proximal_mu = proximal_mu
        self.dp_epsilon = dp_epsilon
        self.dp_delta = dp_delta
        self.convergence_threshold = convergence_threshold
        
        self.round_history = []
        self.has_converged = False
    
    def aggregate_weights(self, client_weights: List, 
                         client_samples: List[int],
                         client_metrics: Optional[List[Dict]] = None,
                         global_weights: Optional[List] = None) -> List:
        """Aggregate model weights from multiple clients.
        
        Args:
            client_weights: List of weight arrays from each client
            client_samples: Number of training samples per client
            client_metrics: Optional metrics from each client (for quality weighting)
            global_weights: Previous round global weights (for FedProx)
            
        Returns:
            Aggregated weight arrays
        """
        if self.aggregation_method == 'fedavg':
            return self._fedavg(client_weights, client_samples)
        elif self.aggregation_method == 'fedprox':
            return self._fedprox(client_weights, client_samples, global_weights)
        elif self.aggregation_method == 'quality_weighted':
            return self._quality_weighted(client_weights, client_metrics)
        else:
            return self._fedavg(client_weights, client_samples)
    
    def _fedavg(self, client_weights, client_samples):
        """Standard Federated Averaging."""
        total_samples = sum(client_samples)
        
        aggregated = []
        for layer_idx in range(len(client_weights[0])):
            weighted_sum = np.zeros_like(client_weights[0][layer_idx])
            
            for client_idx, weights in enumerate(client_weights):
                weight_factor = client_samples[client_idx] / total_samples
                weighted_sum += weights[layer_idx] * weight_factor
            
            aggregated.append(weighted_sum)
        
        return aggregated
    
    def _fedprox(self, client_weights, client_samples, global_weights=None):
        """FedProx: Adds proximal term for heterogeneous data.
        
        Penalizes client updates that deviate too far from the global model,
        improving convergence on non-IID data.
        """
        # First do standard FedAvg
        aggregated = self._fedavg(client_weights, client_samples)
        
        # Apply proximal regularization if we have previous global weights
        if global_weights is not None:
            for layer_idx in range(len(aggregated)):
                # Proximal term: μ/2 * ||w - w_global||²
                diff = aggregated[layer_idx] - global_weights[layer_idx]
                aggregated[layer_idx] -= self.proximal_mu * diff
        
        return aggregated
    
    def _quality_weighted(self, client_weights, client_metrics):
        """Weight aggregation by client model quality (inverse error)."""
        if client_metrics is None:
            # Fall back to equal weights
            n = len(client_weights)
            equal_samples = [1] * n
            return self._fedavg(client_weights, equal_samples)
        
        # Use inverse RMSE as quality weight
        quality_scores = []
        for metrics in client_metrics:
            rmse = metrics.get('RMSE', metrics.get('rmse', 1.0))
            quality_scores.append(1.0 / max(rmse, 1e-6))
        
        total_quality = sum(quality_scores)
        quality_weights = [q / total_quality for q in quality_scores]
        
        aggregated = []
        for layer_idx in range(len(client_weights[0])):
            weighted_sum = np.zeros_like(client_weights[0][layer_idx])
            
            for client_idx, weights in enumerate(client_weights):
                weighted_sum += weights[layer_idx] * quality_weights[client_idx]
            
            aggregated.append(weighted_sum)
        
        return aggregated
    
    def add_differential_privacy(self, weights, sensitivity=1.0):
        """Add calibrated noise for differential privacy.
        
        Uses Gaussian mechanism to add noise proportional to
        the sensitivity and privacy budget.
        
        Args:
            weights: Model weights to privatize
            sensitivity: L2 sensitivity of the query
            
        Returns:
            Noisy weights satisfying (epsilon, delta)-DP
        """
        sigma = sensitivity * np.sqrt(2 * np.log(1.25 / self.dp_delta)) / self.dp_epsilon
        
        noisy_weights = []
        for w in weights:
            noise = np.random.normal(0, sigma, size=w.shape)
            noisy_weights.append(w + noise)
        
        return noisy_weights
    
    def check_convergence(self, current_weights, previous_weights=None):
        """Monitor convergence by tracking weight changes.
        
        Args:
            current_weights: Current round weights
            previous_weights: Previous round weights
            
        Returns:
            dict with convergence status and metrics
        """
        if previous_weights is None:
            return {
                'converged': False,
                'weight_change': float('inf'),
                'round': len(self.round_history) + 1
            }
        
        # Calculate total weight change
        total_change = 0
        total_params = 0
        for curr, prev in zip(current_weights, previous_weights):
            total_change += np.sum((curr - prev) ** 2)
            total_params += curr.size
        
        avg_change = np.sqrt(total_change / max(total_params, 1))
        
        self.round_history.append({
            'round': len(self.round_history) + 1,
            'weight_change': float(avg_change)
        })
        
        self.has_converged = avg_change < self.convergence_threshold
        
        return {
            'converged': self.has_converged,
            'weight_change': float(avg_change),
            'round': len(self.round_history),
            'history': self.round_history[-5:]  # Last 5 rounds
        }
    
    def get_convergence_history(self):
        """Return full convergence history."""
        return {
            'rounds': len(self.round_history),
            'converged': self.has_converged,
            'history': self.round_history
        }
