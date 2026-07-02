# macOS UI Migration Guide

## Overview

This document outlines the migration from the existing UI system to a complete macOS-style interface that follows Apple's Human Interface Guidelines (HIG). The new design system provides a native macOS experience while maintaining all existing functionality and APIs.

## 🎯 Migration Goals

- **Visual Consistency**: All UI elements match macOS design language
- **Native Feel**: Interactions and animations feel native to macOS
- **Accessibility**: Maintain and enhance accessibility features
- **Responsiveness**: Desktop-first with mobile fallbacks
- **Performance**: Optimized for smooth animations and interactions
- **Backwards Compatibility**: Existing APIs and business logic preserved

## 📋 Migration Checklist

### Phase 1: Foundation (✅ Completed)
- [x] **Theme Tokens**: macOS color palette, spacing, typography
- [x] **Button Component**: macOS-style buttons with variants
- [x] **Input Component**: macOS-style text inputs with focus states
- [x] **Card Component**: macOS-style containers with variants
- [x] **Modal Component**: macOS-style dialogs with backdrop blur
- [x] **Table Component**: macOS-style data tables with sorting
- [x] **Tooltip Component**: macOS-style contextual help
- [x] **Icon Component**: SF Symbols-like icon system

### Phase 2: Layout Components (✅ Completed)
- [x] **Sidebar Component**: macOS-style navigation sidebar
- [x] **Header Component**: macOS-style window header
- [x] **Tab Bar**: macOS-style tabbed interface
- [x] **Navigation**: macOS-style navigation patterns
- [x] **Toolbar**: macOS-style toolbars

### Phase 3: Form Components
- [ ] **Checkbox**: macOS-style checkboxes
- [ ] **Radio Button**: macOS-style radio buttons
- [ ] **Switch**: macOS-style toggles
- [ ] **Slider**: macOS-style sliders
- [ ] **Segmented Control**: macOS-style segmented controls
- [ ] **Date Picker**: macOS-style date selection
- [ ] **Color Picker**: macOS-style color selection

### Phase 4: Advanced Components
- [ ] **Popover**: macOS-style popover menus
- [ ] **Dropdown**: macOS-style dropdown menus
- [ ] **Context Menu**: macOS-style contextual menus
- [ ] **Alert**: macOS-style alert dialogs
- [ ] **Sheet**: macOS-style bottom sheets
- [ ] **Progress**: macOS-style progress indicators

### Phase 5: Data Visualization
- [ ] **Chart Components**: macOS-style charts and graphs
- [ ] **Gauge**: macOS-style gauge components
- [ ] **Sparkline**: macOS-style mini charts
- [ ] **Heatmap**: macOS-style heatmaps
- [ ] **Timeline**: macOS-style timeline components

## 🎨 Design System Overview

### Color Palette
```css
/* Light Mode */
--mac-bg-primary: #ffffff;
--mac-bg-secondary: #f8f9fa;
--mac-bg-tertiary: #f1f3f4;
--mac-text-primary: #1d1d1f;
--mac-text-secondary: #86868b;
--mac-accent-blue: #007aff;

/* Dark Mode */
--mac-bg-primary: #1d1d1f;
--mac-bg-secondary: #2d2d30;
--mac-bg-tertiary: #3d3d40;
--mac-text-primary: #f5f5f7;
--mac-text-secondary: #a1a1a6;
```

### Typography
- **Font Stack**: `-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif`
- **Sizes**: 11px, 12px, 13px, 15px, 17px, 22px, 28px
- **Weights**: 400 (regular), 500 (medium), 600 (semibold), 700 (bold)

### Spacing Grid
- **Base Unit**: 8px
- **Scale**: 4px, 8px, 12px, 16px, 20px, 24px, 32px, 40px, 48px, 64px

### Border Radius
- **Small**: 4px
- **Medium**: 6px
- **Large**: 8px
- **Extra Large**: 12px
- **Full**: 9999px

### Shadows
- **Small**: `0 1px 3px rgba(0, 0, 0, 0.12), 0 1px 2px rgba(0, 0, 0, 0.24)`
- **Medium**: `0 4px 12px rgba(0, 0, 0, 0.15)`
- **Large**: `0 10px 25px rgba(0, 0, 0, 0.15)`
- **Extra Large**: `0 20px 40px rgba(0, 0, 0, 0.15)`

## 🔧 Implementation Guide

### Using macOS Components

```javascript
// Import macOS components
import { Button, Card, Input, Modal } from '../components/ui/macos';

// Use in your components
const MyComponent = () => {
  return (
    <Card padding="large" interactive>
      <CardHeader>
        <CardTitle>My macOS Card</CardTitle>
        <CardDescription>A beautiful card component</CardDescription>
      </CardHeader>
      <CardContent>
        <Input
          label="Username"
          placeholder="Enter your username"
          hint="This will be your display name"
        />
        <Button variant="primary" size="large">
          Submit
        </Button>
      </CardContent>
    </Card>
  );
};
```

### Migration Pattern

1. **Identify Component Usage**: Find where UI components are used
2. **Import macOS Version**: Replace imports with macOS components
3. **Update Props**: Adjust props to match macOS API
4. **Test Functionality**: Ensure business logic still works
5. **Verify Styling**: Check visual consistency

### Backwards Compatibility

```javascript
// Old imports still work for gradual migration
import { Button as LegacyButton } from '../ui/native';
import { Button as MacButton } from '../ui/macos';

// Can use both during transition period
<LegacyButton>Legacy</LegacyButton>
<MacButton>macOS</MacButton>
```

## 🚀 Quick Start

### 1. Import macOS Theme
```javascript
import '../theme/macos-tokens.css';
```

### 2. Use macOS Components
```javascript
import { Button, Card, Input } from '../components/ui/macos';

export default function MyPage() {
  return (
    <div style={{ fontFamily: 'var(--mac-font-family)' }}>
      <Card>
        <CardHeader>
          <CardTitle>Welcome to macOS UI</CardTitle>
        </CardHeader>
        <CardContent>
          <Input label="Email" placeholder="your@email.com" />
          <Button variant="primary">Continue</Button>
        </CardContent>
      </Card>
    </div>
  );
}
```

### 3. Responsive Design
```css
/* Desktop-first responsive design */
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

## 🎭 Animation Guidelines

### macOS Animation Principles
- **Duration**: 120–260ms for most interactions
- **Easing**: `cubic-bezier(0.2, 0.8, 0.2, 1)` (ease-out)
- **Scale**: Subtle transforms (scale, translate)
- **Opacity**: Gentle fade transitions

### Common Animations
```css
/* Fade in */
@keyframes mac-fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* Slide up */
@keyframes mac-slide-up {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
```

## ♿ Accessibility Features

### Focus Management
- **Focus Rings**: 2px blue outline with offset
- **Focus Trap**: Modal focus management
- **Keyboard Navigation**: Full keyboard support
- **Screen Readers**: Proper ARIA attributes

### Motion Preferences
```css
@media (prefers-reduced-motion: reduce) {
  /* Disable animations for users who prefer reduced motion */
  * {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

### High Contrast
```css
@media (prefers-contrast: high) {
  /* Enhanced borders and contrast for accessibility */
  .mac-button {
    border-width: 2px;
  }
}
```

## 📱 Responsive Design

### Breakpoints
- **Desktop**: 1024px+
- **Tablet**: 768px–1023px
- **Mobile**: 320px–767px

### Touch Optimizations
```css
@media (hover: none) and (pointer: coarse) {
  /* Larger touch targets for mobile */
  .mac-button {
    min-height: 44px;
    min-width: 44px;
  }
}
```

## 🔄 Migration Strategy

### Gradual Migration
1. **Phase 1**: Core components (Button, Input, Card)
2. **Phase 2**: Layout components (Sidebar, Header)
3. **Phase 3**: Form components (Checkbox, Radio, etc.)
4. **Phase 4**: Advanced components (Popover, Dropdown)
5. **Phase 5**: Data visualization (Charts, Tables)

### Testing Approach
1. **Visual Testing**: Screenshot comparisons
2. **Functional Testing**: Business logic verification
3. **Accessibility Testing**: Screen reader and keyboard testing
4. **Performance Testing**: Animation and interaction performance

### Rollback Plan
- **Backup Branches**: Keep pre-migration branches
- **Feature Flags**: Enable/disable macOS UI per component
- **Gradual Rollout**: Deploy to subsets of users first

## 🛠 Development Workflow

### Creating New Components
1. **Study HIG**: Review Apple's Human Interface Guidelines
2. **Implement Base**: Create component with basic functionality
3. **Add Variants**: Support different sizes and states
4. **Test Accessibility**: Ensure WCAG compliance
5. **Add Animations**: Implement smooth transitions
6. **Document**: Update component documentation

### Component Structure
```javascript
/**
 * macOS-style Component
 * Brief description following HIG
 */
const Component = React.forwardRef(({
  // Props following macOS patterns
  variant = 'default',
  size = 'default',
  disabled = false,
  // ... other props
}, ref) => {
  // Implementation with macOS styling
  return (
    <div ref={ref} className="mac-component">
      {/* Component content */}
    </div>
  );
});
```

## 📚 Resources

### Apple Design Resources
- [Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/)
- [macOS Design](https://developer.apple.com/design/human-interface-guidelines/macos/overview/)
- [SF Symbols](https://developer.apple.com/sf-symbols/)

### Implementation References
- [macOS Color Palette](https://developer.apple.com/design/human-interface-guidelines/macos/visual-design/color/)
- [Typography Guidelines](https://developer.apple.com/design/human-interface-guidelines/macos/visual-design/typography/)
- [Layout Guidelines](https://developer.apple.com/design/human-interface-guidelines/macos/visual-design/layout/)

## ✅ Migration Status

### Completed ✅
- ✅ macOS theme tokens and CSS variables
- ✅ Button component with variants and hover effects
- ✅ Input component with focus states and validation
- ✅ Card component with variants and interactive states
- ✅ Modal component with backdrop blur and animations
- ✅ Table component with sorting and hover states
- ✅ Tooltip component with intelligent positioning
- ✅ Icon component with SF Symbols-like icons
- ✅ Badge component with color variants
- ✅ Progress component (linear and circular)
- ✅ Avatar component with status indicators
- ✅ Sidebar component with collapsible navigation
- ✅ Header component with breadcrumbs and user controls
- ✅ **All main pages migrated to macOS components**
- ✅ **AdminPanel, DoctorPanel, CashierPanel, PatientPanel**
- ✅ **Specialist panels (Cardiologist, Dermatologist, Dentist)**

### In Progress 🔄
- Form components (Checkbox, Radio, Switch, etc.)
- Advanced components (Popover, Dropdown, Alert, etc.)

### Planned 📋
- Data visualization components (Charts, Gauges, etc.)
- Layout components (TabBar, Navigation, Toolbar, etc.)

## 🚀 Next Steps

1. **Implement Form Components**: Create macOS-style checkboxes, radio buttons, switches
2. **Add Advanced Components**: Implement popovers, dropdowns, alerts
3. **Create Data Visualization**: Build charts, gauges, and other data components
4. **Performance Optimization**: Ensure smooth animations and interactions
5. **Accessibility Audit**: Comprehensive accessibility testing
6. **User Testing**: Collect feedback on the new macOS experience

## 💡 Tips for Migration

1. **Start Small**: Migrate one component at a time
2. **Test Thoroughly**: Verify functionality after each change
3. **Use Feature Flags**: Enable macOS UI for specific users/components
4. **Document Changes**: Keep detailed migration notes
5. **Gather Feedback**: Collect user feedback during rollout
6. **Monitor Performance**: Track animation and interaction performance

## 🎯 Success Metrics

- **Visual Consistency**: 100% of UI elements follow macOS design
- **Performance**: No degradation in animation smoothness
- **Accessibility**: WCAG 2.1 AA compliance maintained
- **User Experience**: Native macOS feel achieved
- **Maintainability**: Clean, documented component architecture

---

*This migration guide will be updated as more components are implemented and the macOS UI system evolves.*

