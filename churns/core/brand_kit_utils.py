"""
Brand Kit Utility Functions
Provides color extraction, harmony generation, and other brand kit related utilities.

Enhanced: Utilities for analyzing semantic brand colors (roles, ratios) and
building concise prompt snippets for LLM stages with conditional inclusion of
usage ratios only when the user customized them.
"""

import colorsys
import logging
from typing import List, Dict, Any, Tuple, Optional
from PIL import Image
import io

logger = logging.getLogger(__name__)


def extract_colors_from_image(image_data: bytes) -> List[Dict[str, Any]]:
    """
    Extract a color palette from image data using color quantization.
    
    Args:
        image_data: Raw image bytes
        
    Returns:
        List of BrandColor dictionaries with hex, role, label, and ratio fields
        
    Raises:
        ValueError: If image processing fails
    """
    try:
        # Open and process the image
        image = Image.open(io.BytesIO(image_data))
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Resize image for faster processing (max 200x200)
        image.thumbnail((200, 200), Image.Resampling.LANCZOS)
        
        # Extract dominant colors using quantization
        # Reduce to 16 colors and get the most common ones
        quantized = image.quantize(colors=16, method=Image.Quantize.MEDIANCUT)
        palette = quantized.getpalette()
        
        if not palette:
            raise ValueError("Failed to extract color palette from image")
        
        # Convert palette to list of RGB tuples
        colors = []
        for i in range(0, min(48, len(palette)), 3):  # Get up to 16 colors (48/3)
            r, g, b = palette[i:i+3]
            colors.append((r, g, b))
        
        # Sort colors by brightness to get a good variety
        colors_with_brightness = []
        for r, g, b in colors:
            brightness = (r * 299 + g * 587 + b * 114) / 1000
            colors_with_brightness.append(((r, g, b), brightness))
        
        colors_with_brightness.sort(key=lambda x: x[1], reverse=True)
        
        # Select 4 diverse colors: darkest, brightest, and 2 mid-tones
        selected_colors = []
        if len(colors_with_brightness) >= 4:
            # Get brightest
            selected_colors.append(colors_with_brightness[0][0])
            # Get darkest
            selected_colors.append(colors_with_brightness[-1][0])
            # Get two mid-range colors
            mid_point = len(colors_with_brightness) // 2
            selected_colors.append(colors_with_brightness[mid_point][0])
            selected_colors.append(colors_with_brightness[mid_point // 2][0])
        else:
            # Use whatever colors we have
            selected_colors = [color[0] for color in colors_with_brightness]
        
        # Convert to BrandColor objects
        brand_colors = []
        roles = ['primary', 'accent', 'neutral_light', 'neutral_dark']
        
        for i, (r, g, b) in enumerate(selected_colors[:4]):
            hex_color = f"#{r:02x}{g:02x}{b:02x}"
            role = roles[i] if i < len(roles) else 'accent'
            
            brand_colors.append({
                "hex": hex_color,
                "role": role,
                "label": None,
                "ratio": None
            })
        
        logger.info(f"Successfully extracted {len(brand_colors)} colors from image")
        return brand_colors
        
    except Exception as e:
        logger.error(f"Error extracting colors from image: {e}")
        raise ValueError(f"Failed to extract colors from image: {str(e)}")


def generate_color_harmonies(base_color: str, target_role: Optional[str] = None, offset: int = 0) -> Dict[str, Any]:
    """
    Generate color harmony suggestions based on a base color, optionally curated for a specific role.
    
    Args:
        base_color: Hex color string (e.g., '#FF5733')
        target_role: Optional role to curate suggestions for ('accent', 'secondary', 'neutral_light', 'neutral_dark')
        offset: Offset for pagination of suggestions (default: 0)
        
    Returns:
        Dictionary containing harmonies and neutrals, optionally filtered for the target role
        
    Raises:
        ValueError: If color format is invalid
    """
    try:
        # Validate hex color format
        if not base_color.startswith('#') or len(base_color) != 7:
            raise ValueError("Color must be in hex format (e.g., #FF5733)")
        
        # Parse hex color
        hex_color = base_color[1:]  # Remove #
        try:
            r = int(hex_color[0:2], 16) / 255.0
            g = int(hex_color[2:4], 16) / 255.0
            b = int(hex_color[4:6], 16) / 255.0
        except ValueError:
            raise ValueError("Invalid hex color format")
        
        # Convert RGB to HSV for easier color manipulation
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        
        def hsv_to_hex(h: float, s: float, v: float) -> str:
            """Convert HSV to hex color."""
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
        
        harmonies = {
            "complementary": [],
            "analogous": [],
            "triadic": [],
            "split_complementary": []
        }
        
        # Generate more diverse harmonies based on offset
        # Use offset to create variations in saturation and value
        offset_factor = offset * 0.1  # Small variations based on offset
        
        # Complementary (opposite on color wheel) with variations
        comp_h = (h + 0.5) % 1.0
        for i in range(3):  # Generate 3 complementary variations
            s_var = max(0.1, min(1.0, s + (i - 1) * 0.15 + offset_factor))
            v_var = max(0.2, min(1.0, v + (i - 1) * 0.1))
            harmonies["complementary"].append({
                "hex": hsv_to_hex(comp_h, s_var, v_var),
                "role": "accent",
                "label": f"Complementary {i+1}" if i > 0 else "Complementary",
                "ratio": None
            })
        
        # Analogous colors (adjacent on color wheel) with more variations
        analog_offsets = [0.083, -0.083, 0.167, -0.167]  # ±30°, ±60°
        for i, hue_offset in enumerate(analog_offsets):
            analog_h = (h + hue_offset) % 1.0
            s_var = max(0.1, min(1.0, s + (i % 2 - 0.5) * 0.2))
            v_var = max(0.2, min(1.0, v + (i % 2 - 0.5) * 0.15))
            harmonies["analogous"].append({
                "hex": hsv_to_hex(analog_h, s_var, v_var),
                "role": "accent" if i < 2 else "neutral_light",
                "label": f"Analogous {i+1}",
                "ratio": None
            })
        
        # Triadic colors (120 degrees apart) with variations
        triadic_offsets = [0.333, 0.667]  # 120°, 240°
        for i, hue_offset in enumerate(triadic_offsets):
            for j in range(2):  # 2 variations per triadic
                triadic_h = (h + hue_offset) % 1.0
                s_var = max(0.1, min(1.0, s + j * 0.2 - 0.1))
                v_var = max(0.2, min(1.0, v + j * 0.15 - 0.075))
                harmonies["triadic"].append({
                    "hex": hsv_to_hex(triadic_h, s_var, v_var),
                    "role": "accent",
                    "label": f"Triadic {i+1}{chr(97+j)}",  # 1a, 1b, 2a, 2b
                    "ratio": None
                })
        
        # Split complementary (complement ± 30°) with variations
        comp_h = (h + 0.5) % 1.0
        split_offsets = [0.083, -0.083, 0.125, -0.125]  # ±30°, ±45°
        for i, hue_offset in enumerate(split_offsets):
            split_h = (comp_h + hue_offset) % 1.0
            s_var = max(0.1, min(1.0, s + (i % 2 - 0.5) * 0.25))
            v_var = max(0.2, min(1.0, v + (i % 2 - 0.5) * 0.2))
            harmonies["split_complementary"].append({
                "hex": hsv_to_hex(split_h, s_var, v_var),
                "role": "accent",
                "label": f"Split Comp {i+1}",
                "ratio": None
            })
        
        # Add neutral variations of the base color with more diversity
        neutrals = []
        neutral_configs = [
            # Light neutrals
            (0.15, 0.95, "neutral_light", "Light Neutral 1"),
            (0.25, 0.85, "neutral_light", "Light Neutral 2"),
            (0.1, 0.9, "neutral_light", "Light Neutral 3"),
            # Dark neutrals
            (0.3, 0.25, "neutral_dark", "Dark Neutral 1"),
            (0.2, 0.35, "neutral_dark", "Dark Neutral 2"),
            (0.4, 0.2, "neutral_dark", "Dark Neutral 3"),
        ]
        
        for i, (s_factor, v_factor, role, label) in enumerate(neutral_configs):
            # Add slight offset variations
            s_offset = (offset * 0.05) % 0.1
            v_offset = (offset * 0.03) % 0.08
            
            neutral_color = {
                "hex": hsv_to_hex(h, max(0.05, s * s_factor + s_offset), 
                                max(0.1, min(0.95, v * v_factor + v_offset))),
                "role": role,
                "label": label,
                "ratio": None
            }
            neutrals.append(neutral_color)
        
        result = {
            "base_color": base_color,
            "harmonies": harmonies,
            "neutrals": neutrals
        }
        
        # If target_role is specified, curate suggestions for that role
        if target_role:
            result["curated_suggestions"] = _curate_suggestions_for_role(harmonies, neutrals, target_role, offset)
        
        logger.info(f"Successfully generated color harmonies for {base_color}" + 
                   (f" (curated for {target_role})" if target_role else ""))
        return result
        
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Error generating color harmonies: {e}")
        raise ValueError(f"Failed to generate color harmonies: {str(e)}")


def _curate_suggestions_for_role(harmonies: Dict[str, List[Dict[str, Any]]], 
                                neutrals: List[Dict[str, Any]], 
                                target_role: str, 
                                offset: int = 0) -> List[Dict[str, Any]]:
    """
    Curate color suggestions based on the target role.
    
    Args:
        harmonies: Dictionary of harmony types with color suggestions
        neutrals: List of neutral color variations
        target_role: The role to curate suggestions for
        offset: Offset for pagination of suggestions
        
    Returns:
        List of 3-4 curated color suggestions most appropriate for the role
    """
    suggestions = []
    
    if target_role == "accent":
        # For accent colors, prioritize complementary, triadic, and split-complementary
        # Use offset to cycle through different combinations
        all_accent_options = []
        if harmonies["complementary"]:
            all_accent_options.extend(harmonies["complementary"])
        if harmonies["triadic"]:
            all_accent_options.extend(harmonies["triadic"])
        if harmonies["split_complementary"]:
            all_accent_options.extend(harmonies["split_complementary"])
        
        # Apply offset and take up to 4 suggestions
        start_idx = (offset * 2) % max(1, len(all_accent_options))
        suggestions = all_accent_options[start_idx:start_idx + 4]
        if len(suggestions) < 4 and len(all_accent_options) > 4:
            # Wrap around if needed
            remaining = 4 - len(suggestions)
            suggestions.extend(all_accent_options[:remaining])
            
    elif target_role == "secondary":
        # For secondary colors, prioritize analogous colors
        # Use offset to cycle through different combinations
        all_secondary_options = []
        if harmonies["analogous"]:
            all_secondary_options.extend(harmonies["analogous"])
        if harmonies["complementary"]:
            all_secondary_options.extend(harmonies["complementary"])
        if harmonies["triadic"]:
            all_secondary_options.extend(harmonies["triadic"])
        
        # Apply offset and take up to 4 suggestions
        start_idx = (offset * 2) % max(1, len(all_secondary_options))
        suggestions = all_secondary_options[start_idx:start_idx + 4]
        if len(suggestions) < 4 and len(all_secondary_options) > 4:
            # Wrap around if needed
            remaining = 4 - len(suggestions)
            suggestions.extend(all_secondary_options[:remaining])
            
    elif target_role in ["neutral_light", "neutral_dark"]:
        # For neutrals, prioritize neutral variations and some analogous colors
        # Use offset to cycle through different combinations
        all_neutral_options = []
        
        # Add target neutrals
        target_neutrals = [n for n in neutrals if n["role"] == target_role]
        if target_neutrals:
            all_neutral_options.extend(target_neutrals)
        
        # Add some muted analogous colors as neutral alternatives
        for analog in harmonies["analogous"]:
            # Create a more neutral version by reducing saturation
            analog_neutral = analog.copy()
            analog_neutral["role"] = target_role
            analog_neutral["label"] = f"Muted {analog['label']}"
            all_neutral_options.append(analog_neutral)
        
        # Apply offset and take up to 4 suggestions
        if all_neutral_options:
            start_idx = (offset * 2) % max(1, len(all_neutral_options))
            suggestions = all_neutral_options[start_idx:start_idx + 4]
            if len(suggestions) < 4 and len(all_neutral_options) > 4:
                # Wrap around if needed
                remaining = 4 - len(suggestions)
                suggestions.extend(all_neutral_options[:remaining])
    
    # Update role for all suggestions to match target_role
    for suggestion in suggestions:
        suggestion["role"] = target_role
    
    return suggestions[:4]  # Return max 4 suggestions


def validate_brand_colors(colors: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """
    Validate a list of brand colors for format and accessibility.
    
    Args:
        colors: List of BrandColor dictionaries
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    if not colors:
        return True, []
    
    # Validate hex format
    hex_regex = r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$'
    import re
    
    for i, color in enumerate(colors):
        if not isinstance(color, dict):
            errors.append(f"Color {i+1}: Invalid format, expected dictionary")
            continue
            
        hex_color = color.get('hex')
        if not hex_color:
            errors.append(f"Color {i+1}: Missing hex value")
            continue
            
        if not re.match(hex_regex, hex_color):
            errors.append(f"Color {i+1}: Invalid hex format '{hex_color}'")
            
        role = color.get('role')
        if not role:
            errors.append(f"Color {i+1}: Missing role")
        elif role not in ['primary', 'secondary', 'accent', 'neutral_light', 'neutral_dark']:
            errors.append(f"Color {i+1}: Invalid role '{role}'")
            
        ratio = color.get('ratio')
        if ratio is not None and (not isinstance(ratio, (int, float)) or ratio < 0 or ratio > 1):
            errors.append(f"Color {i+1}: Invalid ratio '{ratio}', must be between 0 and 1")
    
    # Check for duplicate colors
    hex_values = [color.get('hex', '').lower() for color in colors]
    duplicates = set([hex_val for hex_val in hex_values if hex_values.count(hex_val) > 1])
    if duplicates:
        errors.append(f"Duplicate colors found: {', '.join(duplicates)}")
    
    is_valid = len(errors) == 0
    return is_valid, errors


def calculate_contrast_ratio(color1: str, color2: str) -> float:
    """
    Calculate WCAG contrast ratio between two hex colors.
    
    Args:
        color1: First hex color
        color2: Second hex color
        
    Returns:
        Contrast ratio (1-21, higher is better contrast)
    """
    def get_luminance(hex_color: str) -> float:
        """Calculate relative luminance of a color."""
        hex_color = hex_color.replace('#', '')
        rgb = [int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4)]
        rgb = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]

    try:
        lum1 = get_luminance(color1)
        lum2 = get_luminance(color2)
        brightest = max(lum1, lum2)
        darkest = min(lum1, lum2)
        return (brightest + 0.05) / (darkest + 0.05)
    except Exception:
        return 1.0  # Return minimum contrast on error


# =====================
# Semantic Color Helpers
# =====================

BASE_ROLE_RATIOS: Dict[str, float] = {
    "primary": 0.6,
    "secondary": 0.3,
    "accent": 0.1,
}

CORE_ROLES = set(BASE_ROLE_RATIOS.keys())


def _is_core_role(role: Optional[str]) -> bool:
    return bool(role) and role in CORE_ROLES


def _group_colors_by_role(colors: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for c in colors or []:
        role = c.get("role") or "unknown"
        grouped.setdefault(role, []).append(c)
    return grouped


def _expected_default_distribution(colors: List[Dict[str, Any]]) -> Dict[Tuple[str, int], float]:
    """
    Compute expected per-color ratios under default intelligent distribution
    (60/30/10 for present core roles, with missing base redistributed equally
    among present roles, and split evenly within a role across its colors).

    Returns mapping of (role, index_within_role) -> expected_ratio.
    """
    grouped = _group_colors_by_role(colors)
    present_core_roles = [r for r in grouped.keys() if _is_core_role(r)]
    if not present_core_roles:
        return {}

    # Total base of present roles
    total_base = sum(BASE_ROLE_RATIOS.get(r, 0.0) for r in present_core_roles)
    missing = max(0.0, 1.0 - total_base)
    redistribution = missing / len(present_core_roles) if present_core_roles else 0.0

    expected: Dict[Tuple[str, int], float] = {}
    for role in present_core_roles:
        role_ratio = BASE_ROLE_RATIOS.get(role, 0.0) + redistribution
        role_colors = grouped.get(role, [])
        if role_colors:
            per_color = role_ratio / len(role_colors)
            for idx_within_role, _c in enumerate(role_colors):
                expected[(role, idx_within_role)] = per_color
    return expected


def analyze_brand_colors(colors: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze semantic brand colors to determine if usage ratios are custom or default-like,
    and provide aggregated summaries.

    Returns dict with:
      - is_custom_mode: bool
      - core_roles_present: List[str]
      - role_to_colors: Dict[str, List[Dict]]
      - role_ratio_sums: Dict[str, float] (only for core roles, if ratios present)
      - neutrals: List[Dict]
    """
    grouped = _group_colors_by_role(colors)
    core_roles_present = [r for r in grouped.keys() if _is_core_role(r)]
    neutrals = [c for r, lst in grouped.items() for c in lst if r and "neutral" in r]

    # Quick path: explicit custom flags
    if any(c.get("isCustomRatio") and _is_core_role(c.get("role")) for c in colors):
        is_custom_mode = True
    else:
        # Infer by comparing to expected default distribution if ratios provided
        expected = _expected_default_distribution(colors)
        tolerance = 0.03  # 3 percentage points tolerance
        is_custom_mode = False
        # Build index within role for stable comparison
        role_positions: Dict[str, int] = {}
        for c in colors:
            role = c.get("role")
            if not _is_core_role(role):
                continue
            pos = role_positions.get(role, 0)
            role_positions[role] = pos + 1
            expected_ratio = expected.get((role, pos))
            actual_ratio = c.get("ratio")
            # If actual ratio missing, treat as default-like (we won't include ratios)
            if actual_ratio is None or expected_ratio is None:
                continue
            if abs(actual_ratio - expected_ratio) > tolerance:
                is_custom_mode = True
                break

    # Aggregate role ratio sums if available
    role_ratio_sums: Dict[str, float] = {}
    for role in core_roles_present:
        total = 0.0
        for c in grouped.get(role, []):
            r = c.get("ratio")
            if isinstance(r, (int, float)):
                total += float(r)
        role_ratio_sums[role] = total if total > 0 else 0.0

    return {
        "is_custom_mode": is_custom_mode,
        "core_roles_present": core_roles_present,
        "role_to_colors": {r: grouped.get(r, []) for r in grouped.keys()},
        "role_ratio_sums": role_ratio_sums,
        "neutrals": neutrals,
    }


def build_brand_palette_prompt(colors: List[Dict[str, Any]], layer: str) -> str:
    """
    Build a concise and effective brand palette prompt snippet for an LLM.

    This version combines the original role-based ratio aggregation with an
    enhanced structure for clarity and more actionable guidance. It addresses:
    - Clear headings for structure.
    - A "Key Principle" for the LLM.
    - Consolidated and consistent guidance for neutral colors.
    - Actionable instructions for both 'style' and 'creative' layers.

    Args:
        colors: A list of brand color dictionaries.
        layer: The pipeline layer ('style' or 'creative') to tailor guidance for.

    Returns:
        A formatted markdown string to be used as a prompt component.
    """
    analysis = analyze_brand_colors(colors or [])
    grouped = _group_colors_by_role(colors or [])
    is_custom = analysis["is_custom_mode"]

    # Return early if there are no colors to process.
    if not grouped:
        return ""

    lines: List[str] = ["**Brand Color Palette & Usage Guide:**"]

    # --- Color Definitions ---
    # Core roles first in a specific order
    role_order = ["primary", "secondary", "accent"]
    for role in role_order:
        if role_colors := grouped.get(role, []):
            role_title = role.replace("_", " ").title()
            color_strs = []
            for c in role_colors:
                hex_val = c.get('hex')
                label = c.get('label')
                if label:
                    color_strs.append(f"`{hex_val}` ({label})")
                else:
                    color_strs.append(f"`{hex_val}`")
            lines.append(f"- **{role_title}:** {', '.join(color_strs)}")

    # Consolidate all neutral colors
    neutral_colors = grouped.get("neutral_light", []) + grouped.get("neutral_dark", [])
    if neutral_colors:
        color_strs = [f"`{c.get('hex')}`" for c in neutral_colors]
        lines.append(f"- **Neutral Tones:** {', '.join(color_strs)}")

    lines.append("")  # Add a spacer

    # --- Key Principle ---
    lines.append("**Key Principle:** Create a visually cohesive and on-brand image that respects the color hierarchy.")

    # --- Actionable Guidance ---
    if is_custom:
        lines.append("\n**Usage Instructions (Custom Ratios):**")
        
        usage_parts = []
        # Iterate through colors, respecting role order for presentation
        for role in role_order:
            role_colors = [c for c in (colors or []) if c.get("role") == role]
            for color in role_colors:
                ratio = color.get("ratio")
                if isinstance(ratio, (int, float)) and ratio > 0:
                    pct = int(round(ratio * 100))
                    if pct > 0:
                        hex_val = color.get('hex', '')
                        label = color.get('label')
                        color_desc = f"`{hex_val}`"
                        if label:
                            color_desc += f" ({label})"
                        usage_parts.append(f"{color_desc}: ~{pct}%")
        
        if usage_parts:
            usage_plan = f"Usage Plan: {', '.join(usage_parts)}."
            if layer == "style":
                lines.append(f"- Strictly adhere to the per-color usage plan: **{usage_plan}** Apply this distribution (±5%) across key visual elements.")
            else:  # creative layer
                lines.append(f"- In your `color_palette` output, reflect the per-color usage plan: **{usage_plan}** This guides the final mapping of colors to elements.")
        else:
            # Fallback for safety, though should not be hit if is_custom is true
            lines.append("- Apply colors based on a visual hierarchy: Primary > Secondary > Accent.")

        # Consistent neutral guidance
        lines.append("- Use Neutral Tones functionally for backgrounds, text, and surfaces to ensure balance.")

    else:  # Default-like (semantic)
        lines.append("\n**Usage Instructions (Semantic Roles):**")
        if layer == "style":
            lines.append("- Prioritize colors based on their semantic roles: **Primary > Secondary > Accent**.")
            lines.append("- Build a clear visual hierarchy. Avoid specifying exact percentages; focus on dominance and emphasis.")
        else:  # creative layer
            lines.append("- In your `color_palette` output, establish a clear hierarchy: **Primary > Secondary > Accent**.")
            lines.append("- Let the roles guide color application, not rigid numbers.")
        
        # Consistent neutral guidance
        lines.append("- Use Neutral Tones functionally for backgrounds, text, and surfaces to ensure balance and readability.")

    return "\n".join(lines)