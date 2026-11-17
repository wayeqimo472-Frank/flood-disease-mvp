---
name: Field Atlas Decision Desk
description: Evidence-bound agricultural risk decisions presented as a pale, image-led modular workspace.
colors:
  canvas: "#E8EBE4"
  panel: "#F7F6F1"
  panel-strong: "#FFFEFA"
  ink: "#18211B"
  muted: "#657166"
  forest: "#244632"
  lime: "#A8D53F"
  lime-hover: "#C0EB4F"
  lime-soft: "#E9F2CD"
  line: "#CFD8CB"
  sidebar: "#E0E5DC"
  scrollbar: "#9FAD9B"
  surface-hover: "#F0F3EA"
  placeholder: "#778378"
  hero-fallback: "#5F7755"
  amber: "#A96B20"
  danger: "#A14238"
typography:
  display:
    fontFamily: "Segoe UI Variable Text, Microsoft YaHei UI, Microsoft YaHei, sans-serif"
    fontSize: "40.8px"
    fontWeight: 720
    lineHeight: 1.12
    letterSpacing: "-0.026em"
  headline:
    fontFamily: "Segoe UI Variable Text, Microsoft YaHei UI, Microsoft YaHei, sans-serif"
    fontSize: "21.8px"
    fontWeight: 710
    lineHeight: 1.3
    letterSpacing: "-0.026em"
  title:
    fontFamily: "Segoe UI Variable Text, Microsoft YaHei UI, Microsoft YaHei, sans-serif"
    fontSize: "16.3px"
    fontWeight: 700
    lineHeight: 1.4
    letterSpacing: "-0.026em"
  body:
    fontFamily: "Segoe UI Variable Text, Microsoft YaHei UI, Microsoft YaHei, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.68
    letterSpacing: "0em"
  label:
    fontFamily: "Segoe UI Variable Text, Microsoft YaHei UI, Microsoft YaHei, sans-serif"
    fontSize: "12px"
    fontWeight: 690
    lineHeight: 1.4
    letterSpacing: "0.02em"
rounded:
  xs: "11px"
  control: "13px"
  sm: "14px"
  secondary: "15px"
  md: "18px"
  lg: "20px"
  media: "22px"
  banner: "24px"
  xl: "26px"
  display: "30px"
  pill: "999px"
spacing:
  xs: "6px"
  sm: "10px"
  md: "16px"
  lg: "24px"
  xl: "40px"
components:
  button-primary:
    backgroundColor: "{colors.lime}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "8px 15px"
  button-secondary:
    backgroundColor: "{colors.panel-strong}"
    textColor: "{colors.forest}"
    rounded: "{rounded.sm}"
    padding: "8px 15px"
  chip:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.forest}"
    rounded: "{rounded.sm}"
    padding: "5px 11px"
  module:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "18px"
  metric-primary:
    backgroundColor: "{colors.forest}"
    textColor: "{colors.panel-strong}"
    rounded: "{rounded.lg}"
    padding: "16px 17px"
---

# Design System: Field Atlas Decision Desk

## Overview

**Creative North Star: "The Living Field Atlas"**

The interface treats each assessment as a route through a working field atlas. Large agricultural imagery establishes the operating context, while pale survey-like surfaces hold exact inputs, evidence states, and intervention boundaries. The visual tone is optimistic and contemporary, but never turns uncertainty into a decorative certainty.

Navigation and data controls remain familiar web patterns. The visual world enters through the restrained palette, generous radii, image-led first viewport, survey-card rhythm, and one signature move: a lime route that connects exposure, evidence, and the next operational action.

**Key Characteristics:**

- Pale mineral canvas with warm paper-like modules.
- Electric lime reserved for selection and the next action.
- Large rounded, asymmetric modules instead of a uniform card grid.
- Agricultural photography used as atmosphere and explicitly labeled.
- Dense evidence presented with calm spacing and visible boundaries.

## Colors

The palette combines a cool field-survey neutral range with one high-energy crop accent.

### Primary

- **Signal Lime** (`#A8D53F`): Current navigation, primary actions, the assessment route, and singular emphasis.

### Secondary

- **Deep Field Green** (`#244632`): Priority result surfaces, supporting navigation text, and high-confidence contrast.

### Neutral

- **Mineral Canvas** (`#E8EBE4`): The application ground.
- **Warm Survey Paper** (`#F7F6F1`): Standard modules and form groupings.
- **Bright Field Paper** (`#FFFEFA`): Inputs and compact controls.
- **Field Ink** (`#18211B`): Primary text.
- **Lichens** (`#657166`): Secondary text and explanatory labels.
- **Survey Rule** (`#CFD8CB`): Table borders and compact separators.

### Named Rules

**The One Route Rule.** Lime carries selection and the recommended next action; it is not scattered decoration.

## Typography

**Display Font:** Segoe UI Variable Text with Microsoft YaHei UI fallback
**Body Font:** Segoe UI Variable Text with Microsoft YaHei UI fallback

**Character:** A single modern humanist sans keeps a bilingual operational interface precise and familiar.

### Hierarchy

- **Display** (720, 40.8px, 1.12): Page title only.
- **Headline** (710, 21.8px, 1.3): Section and hero headings.
- **Title** (700, 16.3px, 1.4): Module titles and form groups.
- **Body** (400, 16px, 1.68): Explanations, controls, and long-form evidence.
- **Label** (690, 12px): Chips, metric labels, statuses, and supporting metadata.

## Layout

The desktop shell uses a 248px pale navigation rail and a content column capped at 1360px. The first viewport combines an asymmetric image hero with compact state facts. Content below alternates between wide media modules, small status cards, and dense evidence tables. Tablet layouts wrap larger column groups; phones use a single column and remove any collapsed-sidebar width reservation.

## Elevation & Depth

Primary modules use soft ambient elevation without a competing border. Dense data surfaces use a single light border without shadow. This keeps image-led modules soft while preserving exact table and input boundaries.

### Shadow Vocabulary

- **Survey Lift** (`0 22px 60px rgba(27, 47, 32, 0.09)`): Hero and major image modules.
- **Module Lift** (`0 12px 34px rgba(27, 47, 32, 0.065)`): Form groups, status cards, and route cards.

## Shapes

Corners are consistently generous: 14px for buttons, 18px for inputs and compact cards, 20px for form modules, 26px for major dashboard modules, and 30px for the overview hero. Borders stay hairline and only appear around data and editable controls.

## Components

### Buttons

- **Shape:** 14px rounded rectangle.
- **Primary:** Signal Lime background with Field Ink text.
- **Secondary:** Bright Field Paper with Deep Field Green text.
- **Interaction:** 160ms state transitions; press feedback scales to 0.975.

### Chips

- **Style:** Warm Survey Paper surface, subtle green border, compact pill.
- **Use:** Case, input source, and scope labels.

### Cards / Containers

- **Corner Style:** 18–30px.
- **Background:** Warm Survey Paper or a full-bleed agricultural image.
- **Shadow Strategy:** Soft elevation only, never shadow plus border.
- **Internal Padding:** 18–24px.

### Inputs / Fields

- **Style:** Bright Field Paper, 13px radius, no default outline.
- **Focus:** A restrained lime-tinted ring on the complete control wrapper.
- **Missing state:** Explicitly written as “缺失”; never silently rendered as zero.

### Navigation

- **Style:** Pale mineral sidebar, compact rounded links, Deep Field Green text.
- **Active:** Signal Lime surface with Field Ink text.
- **Mobile:** Collapsed by default, with no reserved empty column.

### Assessment Hero

Full-bleed field photography under a green scrim, a compact status chip, three immediate facts, and one lime next-action control.

## Do's and Don'ts

### Do:

- **Do** use Signal Lime for the current route and primary actions.
- **Do** label atmosphere photography as non-measurement material.
- **Do** keep missing values and evidence boundaries adjacent to results.
- **Do** use image-led modules for orientation and data surfaces for detail.

### Don't:

- **Don't** return to a dark sidebar or generic Streamlit default surface.
- **Don't** use lime as decoration on inactive objects.
- **Don't** place a border and a wide shadow on the same module.
- **Don't** let agricultural imagery imply local observation or forecast data.
