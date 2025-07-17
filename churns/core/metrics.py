"""
Consistency Metrics - Calculate CLIP similarity and color histogram metrics.

This module provides functions to calculate consistency metrics for STYLE_RECIPE presets,
measuring how well new generated images match the original style.
"""

import numpy as np
import logging
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from PIL import Image
import colorsys

logger = logging.getLogger(__name__)

# Optional imports for advanced metrics
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("sentence-transformers not available, CLIP similarity metrics will be disabled")

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.warning("opencv-python not available, advanced color metrics will be disabled")


class ConsistencyMetrics:
    """Calculate consistency metrics for style recipe comparisons."""
    
    def __init__(self):
        self.clip_model = None
        self._initialize_clip_model()
    
    def _initialize_clip_model(self):
        """Initialize CLIP model for image similarity calculation."""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.warning("CLIP model not available - similarity metrics will be disabled")
            return
        
        try:
            # Use a lightweight CLIP model for similarity calculation
            self.clip_model = SentenceTransformer('clip-ViT-B-32')
            logger.info("CLIP model initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize CLIP model: {e}")
            self.clip_model = None
    
    def calculate_consistency_metrics(
        self, 
        original_image_path: str, 
        new_image_path: str,
        original_recipe: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive consistency metrics between two images.
        
        Args:
            original_image_path: Path to the original image from the style recipe
            new_image_path: Path to the newly generated image
            original_recipe: Optional original style recipe data for enhanced metrics
            
        Returns:
            Dictionary containing consistency metrics
        """
        metrics = {
            "clip_similarity": None,
            "color_histogram_similarity": None,
            "color_palette_match": None,
            "overall_consistency_score": None,
            "detailed_metrics": {}
        }
        
        try:
            # Load images
            original_image = Image.open(original_image_path)
            new_image = Image.open(new_image_path)
            
            # Calculate CLIP similarity
            if self.clip_model:
                clip_score = self._calculate_clip_similarity(original_image, new_image)
                metrics["clip_similarity"] = clip_score
                logger.info(f"CLIP similarity: {clip_score:.3f}")
            
            # Calculate color histogram similarity
            hist_score = self._calculate_color_histogram_similarity(original_image, new_image)
            metrics["color_histogram_similarity"] = hist_score
            logger.info(f"Color histogram similarity: {hist_score:.3f}")
            
            # Calculate color palette match
            palette_score = self._calculate_color_palette_match(original_image, new_image)
            metrics["color_palette_match"] = palette_score
            logger.info(f"Color palette match: {palette_score:.3f}")
            
            # Calculate overall consistency score
            consistency_score = self._calculate_overall_consistency(metrics)
            metrics["overall_consistency_score"] = consistency_score
            logger.info(f"Overall consistency: {consistency_score:.3f}")
            
            # Add detailed metrics
            metrics["detailed_metrics"] = {
                "dominant_colors_original": self._extract_dominant_colors(original_image),
                "dominant_colors_new": self._extract_dominant_colors(new_image),
                "brightness_similarity": self._calculate_brightness_similarity(original_image, new_image),
                "contrast_similarity": self._calculate_contrast_similarity(original_image, new_image)
            }
            
        except Exception as e:
            logger.error(f"Error calculating consistency metrics: {e}")
            metrics["error"] = str(e)
        
        return metrics
    
    def _calculate_clip_similarity(self, image1: Image.Image, image2: Image.Image) -> float:
        """Calculate CLIP similarity between two images."""
        if not self.clip_model:
            return 0.0
        
        try:
            # Convert images to embeddings
            embedding1 = self.clip_model.encode(image1)
            embedding2 = self.clip_model.encode(image2)
            
            # Calculate cosine similarity
            similarity = np.dot(embedding1, embedding2) / (
                np.linalg.norm(embedding1) * np.linalg.norm(embedding2)
            )
            
            return float(similarity)
        except Exception as e:
            logger.error(f"Error calculating CLIP similarity: {e}")
            return 0.0
    
    def _calculate_color_histogram_similarity(self, image1: Image.Image, image2: Image.Image) -> float:
        """Calculate color histogram similarity between two images."""
        try:
            # Convert images to RGB if needed
            if image1.mode != 'RGB':
                image1 = image1.convert('RGB')
            if image2.mode != 'RGB':
                image2 = image2.convert('RGB')
            
            # Calculate histograms for each channel
            hist1_r = np.histogram(np.array(image1)[:, :, 0], bins=256, range=(0, 256))[0]
            hist1_g = np.histogram(np.array(image1)[:, :, 1], bins=256, range=(0, 256))[0]
            hist1_b = np.histogram(np.array(image1)[:, :, 2], bins=256, range=(0, 256))[0]
            
            hist2_r = np.histogram(np.array(image2)[:, :, 0], bins=256, range=(0, 256))[0]
            hist2_g = np.histogram(np.array(image2)[:, :, 1], bins=256, range=(0, 256))[0]
            hist2_b = np.histogram(np.array(image2)[:, :, 2], bins=256, range=(0, 256))[0]
            
            # Calculate correlation coefficient for each channel
            corr_r = np.corrcoef(hist1_r, hist2_r)[0, 1]
            corr_g = np.corrcoef(hist1_g, hist2_g)[0, 1]
            corr_b = np.corrcoef(hist1_b, hist2_b)[0, 1]
            
            # Handle NaN values (can occur with uniform colors)
            corr_r = 0.0 if np.isnan(corr_r) else corr_r
            corr_g = 0.0 if np.isnan(corr_g) else corr_g
            corr_b = 0.0 if np.isnan(corr_b) else corr_b
            
            # Average correlation across channels
            avg_correlation = (corr_r + corr_g + corr_b) / 3
            
            return float(avg_correlation)
        except Exception as e:
            logger.error(f"Error calculating color histogram similarity: {e}")
            return 0.0
    
    def _calculate_color_palette_match(self, image1: Image.Image, image2: Image.Image) -> float:
        """Calculate how well the color palettes match between two images."""
        try:
            # Extract dominant colors from both images
            colors1 = self._extract_dominant_colors(image1, k=5)
            colors2 = self._extract_dominant_colors(image2, k=5)
            
            # Calculate the minimum distance between color palettes
            total_distance = 0.0
            for color1 in colors1:
                min_distance = float('inf')
                for color2 in colors2:
                    distance = self._color_distance(color1, color2)
                    min_distance = min(min_distance, distance)
                total_distance += min_distance
            
            # Normalize the distance to a similarity score (0-1)
            # Maximum possible distance is sqrt(3) * 255 for RGB
            max_distance = np.sqrt(3) * 255 * len(colors1)
            similarity = 1.0 - (total_distance / max_distance)
            
            return float(max(0.0, similarity))
        except Exception as e:
            logger.error(f"Error calculating color palette match: {e}")
            return 0.0
    
    def _extract_dominant_colors(self, image: Image.Image, k: int = 5) -> List[Tuple[int, int, int]]:
        """Extract dominant colors from an image using K-means clustering."""
        try:
            # Convert image to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Resize image for faster processing
            image = image.resize((150, 150))
            
            # Convert to numpy array and reshape
            data = np.array(image)
            data = data.reshape((-1, 3))
            
            # Use simple method if scikit-learn is not available
            # Find the most frequent colors
            unique_colors, counts = np.unique(data, axis=0, return_counts=True)
            
            # Sort by frequency and take top k
            sorted_indices = np.argsort(counts)[::-1]
            dominant_colors = unique_colors[sorted_indices[:k]]
            
            return [tuple(color) for color in dominant_colors]
        except Exception as e:
            logger.error(f"Error extracting dominant colors: {e}")
            return []
    
    def _color_distance(self, color1: Tuple[int, int, int], color2: Tuple[int, int, int]) -> float:
        """Calculate Euclidean distance between two RGB colors."""
        return np.sqrt(sum((c1 - c2) ** 2 for c1, c2 in zip(color1, color2)))
    
    def _calculate_brightness_similarity(self, image1: Image.Image, image2: Image.Image) -> float:
        """Calculate brightness similarity between two images."""
        try:
            # Convert to grayscale and calculate mean brightness
            gray1 = image1.convert('L')
            gray2 = image2.convert('L')
            
            brightness1 = np.mean(np.array(gray1))
            brightness2 = np.mean(np.array(gray2))
            
            # Calculate similarity (1 - normalized difference)
            max_brightness = 255.0
            similarity = 1.0 - abs(brightness1 - brightness2) / max_brightness
            
            return float(similarity)
        except Exception as e:
            logger.error(f"Error calculating brightness similarity: {e}")
            return 0.0
    
    def _calculate_contrast_similarity(self, image1: Image.Image, image2: Image.Image) -> float:
        """Calculate contrast similarity between two images."""
        try:
            # Convert to grayscale and calculate standard deviation (proxy for contrast)
            gray1 = image1.convert('L')
            gray2 = image2.convert('L')
            
            contrast1 = np.std(np.array(gray1))
            contrast2 = np.std(np.array(gray2))
            
            # Calculate similarity (1 - normalized difference)
            max_contrast = 255.0  # Maximum possible standard deviation
            similarity = 1.0 - abs(contrast1 - contrast2) / max_contrast
            
            return float(similarity)
        except Exception as e:
            logger.error(f"Error calculating contrast similarity: {e}")
            return 0.0
    
    def _calculate_overall_consistency(self, metrics: Dict[str, Any]) -> float:
        """Calculate overall consistency score from individual metrics."""
        try:
            scores = []
            weights = []
            
            # CLIP similarity has the highest weight
            if metrics.get("clip_similarity") is not None:
                scores.append(metrics["clip_similarity"])
                weights.append(0.5)
            
            # Color histogram similarity
            if metrics.get("color_histogram_similarity") is not None:
                scores.append(metrics["color_histogram_similarity"])
                weights.append(0.3)
            
            # Color palette match
            if metrics.get("color_palette_match") is not None:
                scores.append(metrics["color_palette_match"])
                weights.append(0.2)
            
            if not scores:
                return 0.0
            
            # Normalize weights
            total_weight = sum(weights)
            weights = [w / total_weight for w in weights]
            
            # Calculate weighted average
            overall_score = sum(score * weight for score, weight in zip(scores, weights))
            
            return float(overall_score)
        except Exception as e:
            logger.error(f"Error calculating overall consistency: {e}")
            return 0.0
    
    def format_consistency_score(self, score: float) -> str:
        """Format consistency score as a percentage with descriptive text."""
        if score is None:
            return "N/A"
        
        percentage = int(score * 100)
        
        if percentage >= 90:
            return f"{percentage}% (Excellent)"
        elif percentage >= 80:
            return f"{percentage}% (Very Good)"
        elif percentage >= 70:
            return f"{percentage}% (Good)"
        elif percentage >= 60:
            return f"{percentage}% (Fair)"
        else:
            return f"{percentage}% (Poor)"


def calculate_consistency_metrics(original_image_path: str, new_image_path: str, original_recipe: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Convenience function to calculate consistency metrics.
    
    Args:
        original_image_path: Path to the original image from the style recipe
        new_image_path: Path to the newly generated image
        original_recipe: Optional original style recipe data
        
    Returns:
        Dictionary containing consistency metrics
    """
    metrics_calculator = ConsistencyMetrics()
    return metrics_calculator.calculate_consistency_metrics(
        original_image_path, new_image_path, original_recipe
    ) 