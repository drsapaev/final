# macOS UI Quick Start

## 🚀 Getting Started

The entire UI has been transformed to follow Apple's Human Interface Guidelines. Here's how to use the new macOS-style components:

### 1. Import Components

```javascript
import {
  Button,
  Input,
  Card,
  Modal,
  Table,
  Icon,
  Badge,
  Progress,
  Avatar,
  Sidebar,
  Header
} from '../components/ui/macos';
```

### 2. Use macOS Theme

```javascript
import '../theme/macos-tokens.css';
```

### 3. Basic Usage

```javascript
const MyPage = () => {
  return (
    <div style={{ fontFamily: 'var(--mac-font-family)' }}>
      <Header
        title="My macOS App"
        user={{ name: 'John Doe', status: 'online' }}
      />

      <div style={{ display: 'flex' }}>
        <Sidebar
          items={[
            { id: 'home', label: 'Home', icon: 'house' },
            { id: 'settings', label: 'Settings', icon: 'gear' }
          ]}
          activeItem="home"
        />

        <div style={{ flex: 1, padding: '20px' }}>
          <Card>
            <Card.Header>
              <Card.Title>Welcome to macOS UI</Card.Title>
            </Card.Header>
            <Card.Content>
              <Input label="Name" placeholder="Enter your name" />
              <Button variant="primary">Submit</Button>
            </Card.Content>
          </Card>
        </div>
      </div>
    </div>
  );
};
```

## 🎨 Design System

### Color Palette
- **Primary**: `#007aff` (macOS blue)
- **Success**: `#34c759` (macOS green)
- **Warning**: `#ff9500` (macOS orange)
- **Danger**: `#ff3b30` (macOS red)

### Typography
- **Font**: `-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display"`
- **Sizes**: 11px, 12px, 13px, 15px, 17px, 22px, 28px

### Spacing
- **Base**: 8px grid system
- **Scale**: 4px, 8px, 12px, 16px, 20px, 24px, 32px, 40px, 48px, 64px

## 🔧 Component Reference

### Button Variants
```javascript
<Button variant="primary">Primary</Button>
<Button variant="secondary">Secondary</Button>
<Button variant="outline">Outline</Button>
<Button variant="ghost">Ghost</Button>
<Button variant="success">Success</Button>
<Button variant="warning">Warning</Button>
<Button variant="danger">Danger</Button>
```

### Input States
```javascript
<Input label="Email" type="email" error="Invalid email" />
<Input label="Password" type="password" hint="Minimum 8 characters" />
<Input disabled placeholder="Disabled input" />
```

### Card Layout
```javascript
<Card interactive onClick={() => console.log('Clicked')}>
  <Card.Header>
    <Card.Title>Card Title</Card.Title>
    <Card.Description>Card description</Card.Description>
  </Card.Header>
  <Card.Content>
    <p>Card content goes here</p>
  </Card.Content>
  <Card.Footer>
    <Button variant="outline">Cancel</Button>
    <Button variant="primary">Save</Button>
  </Card.Footer>
</Card>
```

## 📱 Responsive Design

The system is **desktop-first** with mobile fallbacks:

```css
/* Desktop (default) */
.my-component {
  /* Desktop styles */
}

/* Tablet */
@media (max-width: 1024px) {
  .my-component {
    /* Tablet adjustments */
  }
}

/* Mobile */
@media (max-width: 768px) {
  .my-component {
    /* Mobile layout */
  }
}
```

## ♿ Accessibility

- **Focus Management**: Automatic focus rings and tab order
- **Screen Readers**: Proper ARIA attributes
- **Keyboard Navigation**: Full keyboard support
- **Motion Preferences**: Respects `prefers-reduced-motion`
- **High Contrast**: Enhanced contrast for accessibility

## 🎭 Theme Support

### Light Mode (Default)
- Clean, bright interface
- High contrast for readability

### Dark Mode
- Automatically adapts with `prefers-color-scheme`
- Reduced eye strain in low light
- Maintains contrast ratios

## 🚀 Performance

- **Optimized Animations**: Hardware-accelerated transforms
- **Smooth Transitions**: 120-260ms with proper easing
- **Touch Optimization**: 44px minimum touch targets
- **Reduced Motion**: Respects user preferences

## 📋 Migration Status

✅ **Completed Components:**
- Theme tokens and CSS variables
- Button with 7 variants and hover effects
- Input with focus states and validation
- Card with interactive states and variants
- Modal with backdrop blur and animations
- Table with sorting and hover states
- Tooltip with intelligent positioning
- Icon with 30+ SF Symbols-like icons
- Badge with color variants
- Progress (linear and circular)
- Avatar with status indicators
- Sidebar with collapsible navigation
- Header with breadcrumbs and user controls

🔄 **Next Phase:**
- Form components (Checkbox, Radio, Switch)
- Advanced components (Popover, Dropdown)
- Data visualization (Charts, Gauges)

## 🎯 Key Benefits

1. **Native macOS Experience** - Follows Apple's HIG
2. **Consistent Design** - Unified visual language
3. **Performance Optimized** - Smooth animations and interactions
4. **Accessibility First** - WCAG 2.1 AA compliant
5. **Responsive Design** - Works across all device sizes
6. **Dark Mode Ready** - Automatic light/dark adaptation
7. **Touch Optimized** - Perfect for hybrid devices
8. **Future Proof** - Extensible component architecture

## 📚 Resources

- [Apple HIG](https://developer.apple.com/design/human-interface-guidelines/)
- [Migration Guide](MACOS_UI_MIGRATION_README.md)
- [Component Demo](src/components/examples/MacOSDemo.jsx)

---

**🎉 Your UI is now a native macOS experience!**

