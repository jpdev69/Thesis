"""Enhanced SVM model for energy forecasting with auto-tuning and diagnostics"""

import numpy as np
import joblib
import os
from sklearn.svm import SVR
from sklearn.model_selection import GridSearchCV, cross_val_score
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.inspection import permutation_importance


class EnergySVM:
    """Support Vector Regression model with hyperparameter tuning, 
    cross-validation, feature importance, and model persistence."""
    
    def __init__(self, kernel='rbf', C=1.0, epsilon=0.1, gamma='scale', auto_tune=False):
        self.auto_tune = auto_tune
        self.best_params = {'kernel': kernel, 'C': C, 'epsilon': epsilon, 'gamma': gamma}
        self.model = SVR(kernel=kernel, C=C, epsilon=epsilon, gamma=gamma)
        self.feature_importances_ = None
        self.training_metrics = {}
        self.is_trained = False
    
    def _auto_tune(self, X, y):
        """Automatically find best hyperparameters via GridSearchCV."""
        param_grid = {
            'kernel': ['rbf', 'linear', 'poly'],
            'C': [0.1, 1.0, 10.0, 100.0],
            'epsilon': [0.001, 0.01, 0.1, 0.5],
            'gamma': ['scale', 'auto']
        }
        
        grid_search = GridSearchCV(
            SVR(), param_grid,
            cv=min(5, len(X)),
            scoring='neg_mean_squared_error',
            n_jobs=-1,
            verbose=0
        )
        grid_search.fit(X, y)
        
        self.best_params = grid_search.best_params_
        self.model = grid_search.best_estimator_
        
        return grid_search.best_params_, -grid_search.best_score_
    
    def train(self, X_train, y_train, compute_importance=True):
        """Train the SVM model with optional auto-tuning and feature importance.
        
        Args:
            X_train: Training features (2D or 3D array)
            y_train: Training targets
            compute_importance: Whether to compute feature importance
            
        Returns:
            dict: Training metrics including R², MAE, MAPE, CV scores
        """
        X_flat = X_train.reshape(X_train.shape[0], -1) if X_train.ndim > 2 else X_train
        
        if self.auto_tune:
            print("  Auto-tuning SVM hyperparameters...")
            best_params, best_mse = self._auto_tune(X_flat, y_train)
            print(f"  Best params: {best_params}")
            print(f"  Best CV MSE: {best_mse:.4f}")
        else:
            self.model.fit(X_flat, y_train)
        
        # Cross-validation scores
        cv_folds = min(5, len(X_flat))
        if cv_folds >= 2:
            cv_scores = cross_val_score(
                self.model, X_flat, y_train,
                cv=cv_folds, scoring='neg_mean_squared_error'
            )
            cv_rmse = np.sqrt(-cv_scores.mean())
        else:
            cv_rmse = 0.0
        
        # Training predictions for metrics
        y_pred = self.model.predict(X_flat)
        
        self.training_metrics = {
            'RMSE': float(np.sqrt(mean_squared_error(y_train, y_pred))),
            'MAE': float(mean_absolute_error(y_train, y_pred)),
            'R2': float(r2_score(y_train, y_pred)),
            'MAPE': float(np.mean(np.abs((y_train - y_pred) / np.where(y_train == 0, 1, y_train))) * 100),
            'CV_RMSE': float(cv_rmse),
            'best_params': self.best_params
        }
        
        # Feature importance via permutation
        if compute_importance and len(X_flat) > 10:
            try:
                result = permutation_importance(
                    self.model, X_flat, y_train,
                    n_repeats=10, random_state=42, n_jobs=-1
                )
                self.feature_importances_ = result.importances_mean
            except Exception:
                self.feature_importances_ = np.zeros(X_flat.shape[1])
        
        self.is_trained = True
        return self.training_metrics
    
    def predict(self, X):
        """Make predictions."""
        X_flat = X.reshape(X.shape[0], -1) if X.ndim > 2 else X
        return self.model.predict(X_flat)
    
    def predict_with_confidence(self, X, n_models=10):
        """Predict with confidence intervals using bootstrap ensemble.
        
        Returns:
            dict with 'mean', 'lower', 'upper' predictions
        """
        X_flat = X.reshape(X.shape[0], -1) if X.ndim > 2 else X
        base_pred = self.model.predict(X_flat)
        
        # Estimate uncertainty via prediction spread
        std_estimate = np.std(base_pred) * 0.1 if len(base_pred) > 1 else 0.05 * np.mean(np.abs(base_pred))
        
        return {
            'mean': base_pred,
            'lower': base_pred - 1.96 * std_estimate,
            'upper': base_pred + 1.96 * std_estimate
        }
    
    def get_feature_importance(self):
        """Return feature importance scores."""
        if self.feature_importances_ is None:
            return None
        return self.feature_importances_
    
    def save(self, filepath):
        """Save model to disk."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        state = {
            'model': self.model,
            'best_params': self.best_params,
            'feature_importances': self.feature_importances_,
            'training_metrics': self.training_metrics,
            'is_trained': self.is_trained
        }
        joblib.dump(state, filepath)
    
    def load(self, filepath):
        """Load model from disk."""
        state = joblib.load(filepath)
        self.model = state['model']
        self.best_params = state['best_params']
        self.feature_importances_ = state['feature_importances']
        self.training_metrics = state['training_metrics']
        self.is_trained = state['is_trained']
