# Design System Reference

## Color Palette

### Backgrounds
- Page background: `#0F0F0F`
- Card background: `#1A1A1A`
- Card border: `#2A2A2A`
- Input/secondary bg: `#222222`

### Copper (primary feature accent)
- Copper: `#B87333`
- Copper Light: `#D4956B`
- Copper Dark: `#8B4513`
- Copper Glow: `rgba(184,115,51,0.15)`
- Copper tint bg: `rgba(184,115,51,0.05)`
- Copper tint border: `rgba(184,115,51,0.13)`
- Copper pill border: `rgba(184,115,51,0.2)`
- Copper gradient: `linear-gradient(135deg,#B87333,#8B4513)`

### Amber (secondary feature accent)
- Amber: `#F59E0B`
- Amber tint bg: `rgba(245,158,11,0.05)`
- Amber tint border: `rgba(245,158,11,0.13)`
- Amber pill border: `rgba(245,158,11,0.2)`

### Green (improvements/success)
- Green: `#4ADE80`
- Green tint bg: `rgba(74,222,128,0.05)`
- Green tint border: `rgba(74,222,128,0.15)`
- Green pill border: `rgba(74,222,128,0.2)`

### Text
- Warm White (headings): `#FAF8F5`
- Warm Gray (body): `#A09890`
- Muted (footer/captions): `#6B6560`

## Typography

### Font families
- Body/UI: `'DM Sans', Arial, Helvetica, sans-serif`
- Headings/numbers: `Georgia, 'Times New Roman', serif`

### Font import
```html
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
```

### Sizes
- Feature title: 34px (Georgia, 400 weight)
- Secondary feature title: 28px (Georgia, 400 weight)
- Step number: 28px (Georgia, 400 weight, accent color)
- Step title: 16px (DM Sans, 500 weight, Warm White)
- Body text: 13px (DM Sans, 400 weight, Warm Gray)
- Subtitle: 15px (DM Sans, 400 weight, Warm Gray)
- Badge/label: 10px (DM Sans, 600 weight, uppercase, 0.15em letter-spacing)
- Safeguard pill: 11px (DM Sans, 400 weight, Warm Gray)
- Bullet highlight: 12px (DM Sans, 400 weight, Warm Gray)
- Caption/footer: 12px (DM Sans, 400 weight, Muted, italic)
- Callout notice: 11px (DM Sans, 400 weight, accent color)

## Spacing

### Email container
- Max width: 600px
- Side padding: 24px
- Top padding (logo): 40px
- Section divider padding: 40px top/bottom, 60px left/right

### Cards
- Card padding: 20px (step cards), 16px 18px (info cards)
- Card border-radius: 14px (step cards), 12px (info cards), 8px (pills)
- Card gap: 24px between step cards, 12px between info cards, 8px between pills

### Step cards
- Screenshot width: 200px
- Screenshot border-radius: 12px
- Gap between screenshot and text: 20px
- Gap between description and bullets: 14px

## Icons (Unicode only — no SVGs)

### Bullet/accent icons
| Symbol | Unicode | Use for |
|--------|---------|---------|
| ● | `&#9679;` | Bullet points in step highlights |
| ◆ | `&#9670;` | Safeguard/category pills |
| ▶ | `&#9656;` | List items in role cards |

### Semantic icons
| Symbol | Unicode | Use for |
|--------|---------|---------|
| ⚠ | `&#9888;` | Warning/unavailable |
| 📍 | `&#128205;` | Location/outdated |
| 📱 | `&#128241;` | App-only callout |
| 💡 | `&#128161;` | Tip/CTA callout |
| ⭐ | `&#11088;` | Notable/highlight |
| → | `&#8594;` | Arrow/CTA |
| ⓘ | `&#9432;` | Info notice |

### Color the icon with a `<span>` tag
```html
<span style="color:#B87333;">&#9679;</span> Bullet text here
```

## Dividers

Copper gradient divider between sections:
```html
<tr><td style="padding:40px 60px;">
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"><tr>
    <td style="height:1px;background:linear-gradient(90deg,transparent,rgba(184,115,51,0.25),transparent);font-size:1px;line-height:1px;">&nbsp;</td>
  </tr></table>
</td></tr>
```

## Contributor avatars

### Lead contributor (Engineering lead)
```html
<div style="width:48px;height:48px;border-radius:50%;background:linear-gradient(135deg,#B87333,#8B4513);text-align:center;line-height:48px;font-family:'DM Sans',Arial,sans-serif;font-size:14px;font-weight:600;color:#FAF8F5;border:1.5px solid rgba(184,115,51,0.4);">EW</div>
```

### Other contributors
```html
<div style="width:48px;height:48px;border-radius:50%;background:linear-gradient(135deg,#4A4540,#2A2520);text-align:center;line-height:48px;font-family:'DM Sans',Arial,sans-serif;font-size:14px;font-weight:600;color:#FAF8F5;border:1.5px solid #2A2A2A;">A</div>
```
