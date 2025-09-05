
# Gemini API Image Generation Guide

This document provides a comprehensive guide for developers to use the Gemini API for generating and processing images conversationally. It covers various features like text-to-image, image editing, multi-image composition, and specific prompt strategies.

---

## Features

- **Text-to-Image:** Generate high-quality images from simple or complex text descriptions.
- **Image + Text-to-Image (Editing):** Upload an image and use text prompts to add, remove, or modify elements, change the style, or adjust the color grading.
- **Multi-Image to Image (Composition & Style Transfer):** Use multiple input images to compose a new scene or transfer the style from one image to another.
- **Iterative Refinement:** Engage in a conversational manner to progressively refine images through multiple turns.
- **High-Fidelity Text Rendering:** Generate images containing legible and well-placed text, ideal for logos, diagrams, and posters.

---

## Getting Started

### Python Example for Text-to-Image

```python
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO

client = genai.Client()

prompt = "Create a picture of a nano banana dish in a fancy restaurant with a Gemini theme"

response = client.models.generate_content(
    model="gemini-2.5-flash-image-preview",
    contents=[prompt],
)

for part in response.candidates[0].content.parts:
    if part.text is not None:
        print(part.text)
    elif part.inline_data is not None:
        image = Image.open(BytesIO(part.inline_data.data))
        image.save("generated_image.png")
```

### JavaScript Example for Text-to-Image

```javascript
import { GoogleGenAI, Modality } from "@google/genai";
import * as fs from "node:fs";

async function main() {
  const ai = new GoogleGenAI({});
  const prompt = "Create a picture of a nano banana dish in a fancy restaurant with a Gemini theme";
  const response = await ai.models.generateContent({
    model: "gemini-2.5-flash-image-preview",
    contents: prompt,
  });

  for (const part of response.candidates[0].content.parts) {
    if (part.text) {
      console.log(part.text);
    } else if (part.inlineData) {
      const imageData = part.inlineData.data;
      const buffer = Buffer.from(imageData, "base64");
      fs.writeFileSync("gemini-native-image.png", buffer);
      console.log("Image saved as gemini-native-image.png");
    }
  }
}

main();
```

---

## Image Editing (Text + Image to Image)

You can provide an image along with a text prompt to modify the image by adding/removing elements or style changes.

### Python Example

```python
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO

client = genai.Client()

prompt = "Create a picture of my cat eating a nano-banana in a fancy restaurant under the Gemini constellation"

image = Image.open("/path/to/cat_image.png")

response = client.models.generate_content(
    model="gemini-2.5-flash-image-preview",
    contents=[prompt, image],
)

for part in response.candidates[0].content.parts:
    if part.text is not None:
        print(part.text)
    elif part.inline_data is not None:
        image = Image.open(BytesIO(part.inline_data.data))
        image.save("generated_image.png")
```

### JavaScript Example

```javascript
import { GoogleGenAI, Modality } from "@google/genai";
import * as fs from "node:fs";

async function main() {
  const ai = new GoogleGenAI({});
  const imagePath = "path/to/cat_image.png";
  const imageData = fs.readFileSync(imagePath);
  const base64Image = imageData.toString("base64");
  const prompt = [
    { text: "Create a picture of my cat eating a nano-banana in a fancy restaurant under the Gemini constellation" },
    {
      inlineData: {
        mimeType: "image/png",
        data: base64Image,
      },
    },
  ];

  const response = await ai.models.generateContent({
    model: "gemini-2.5-flash-image-preview",
    contents: prompt,
  });

  for (const part of response.candidates[0].content.parts) {
    if (part.text) {
      console.log(part.text);
    } else if (part.inlineData) {
      const imageData = part.inlineData.data;
      const buffer = Buffer.from(imageData, "base64");
      fs.writeFileSync("gemini-native-image.png", buffer);
      console.log("Image saved as gemini-native-image.png");
    }
  }
}

main();
```

---

## Other Language Examples

- Go, REST API examples are also included in the guide with similar patterns for generating images and editing.

---

## Supported Image Generation Modes

- Text to image(s) and text (interleaved).
- Image(s) and text to image(s) and text (interleaved).
- Multi-turn image editing (chat).

---

## Best Practices for Prompting

1. **Be Hyper-Specific:** Detailed descriptions yield better images.
2. **Provide Context and Intent:** Explain the purpose for better understanding.
3. **Iterate and Refine:** Use conversation turns to refine images.
4. **Use Step-by-Step Instructions:** Break down complex scenes.
5. **Use "Semantic Negative Prompts":** Describe what you want positively.
6. **Control the Camera:** Use photography and cinematic terminology.

---

## Example Prompt Templates

### Photorealistic Scenes

```
A photorealistic [shot type] of [subject], [action or expression], set in [environment]. The scene is illuminated by [lighting description], creating a [mood] atmosphere. Captured with a [camera/lens details], emphasizing [key textures and details]. The image should be in a [aspect ratio] format.
```

### Stylized Illustrations & Stickers

```
A [style] sticker of a [subject], featuring [key characteristics] and a [color palette]. The design should have [line style] and [shading style]. The background must be transparent.
```

### Accurate Text in Images

```
Create a [image type] for [brand/concept] with the text "[text to render]" in a [font style]. The design should be [style description], with a [color scheme].
```

### Product Mockups & Commercial Photography

```
A high-resolution, studio-lit product photograph of a [product description] on a [background surface/description]. The lighting is a [lighting setup] to [lighting purpose]. The camera angle is a [angle type] to showcase [specific feature]. Ultra-realistic, with sharp focus on [key detail]. [Aspect ratio].
```

### Minimalist & Negative Space Design

```
A minimalist composition featuring a single [subject] positioned in the [bottom-right/top-left/etc.] of the frame. The background is a vast, empty [color] canvas, creating significant negative space. Soft, subtle lighting. [Aspect ratio].
```

### Sequential Art (Comic Panel / Storyboard)

```
A single comic book panel in a [art style] style. In the foreground, [character description and action]. In the background, [setting details]. The panel has a [dialogue/caption box] with the text "[Text]". The lighting creates a [mood] mood. [Aspect ratio].
```

---

## Advanced Image Editing Examples

### Adding or Removing Elements

- Use semantic descriptions to match original style and lighting.

### Inpainting (Semantic Masking)

- Define a mask area and change specific elements while preserving the rest.

### Style Transfer

- Transform an image into the artistic style of a famous artist or style.

### Advanced Composition

- Combine multiple images contextually to create a new, composite scene.

### High-Fidelity Detail Preservation

- Preserve critical details like faces or logos when adding new elements.

---

## Limitations

- Best performance in supported languages like English, Spanish (Mexico), Japanese, and Chinese.
- No audio or video input support.
- Works best with up to 3 input images.
- Generated images include a SynthID watermark.

---

For full code samples and more, visit the official Gemini API documentation.
