import React from 'react';

// Simple macOS-style Box (container) that maps common MUI Box props
const Box = React.forwardRef(({ children, style = {}, sx = {}, display, alignItems, justifyContent, gap, mt, mb, mx, my, px, py, p, m, maxWidth, textAlign, ...props }, ref) => {
  const spacing = (v) => (typeof v === 'number' ? v * 8 : v);
  const computedStyle = {
    display,
    alignItems,
    justifyContent,
    gap: gap !== undefined ? spacing(gap) : undefined,
    marginTop: mt !== undefined ? spacing(mt) : (my !== undefined ? spacing(my) : undefined),
    marginBottom: mb !== undefined ? spacing(mb) : (my !== undefined ? spacing(my) : undefined),
    marginLeft: mx !== undefined ? spacing(mx) : undefined,
    marginRight: mx !== undefined ? spacing(mx) : undefined,
    padding: p !== undefined ? spacing(p) : undefined,
    paddingLeft: px !== undefined ? spacing(px) : undefined,
    paddingRight: px !== undefined ? spacing(px) : undefined,
    paddingTop: py !== undefined ? spacing(py) : undefined,
    paddingBottom: py !== undefined ? spacing(py) : undefined,
    maxWidth,
    textAlign,
    ...sx,
    ...style
  };
  return <div ref={ref} style={computedStyle} {...props}>{children}</div>;
});

Box.displayName = 'macOS Box';

export default Box;


