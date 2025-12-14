import React from 'react';

// Simple macOS-style Box (container) that maps common MUI Box props
const Box = React.forwardRef(({ children, style = {}, sx = {}, display, alignItems, justifyContent, gap, mt, mb, mx, my, px, py, p, m, maxWidth, textAlign, ...props }, ref) => {
  const spacing = (v) => (typeof v === 'number' ? v * 8 : v);

  // Calculate padding values - px/py override p for their respective axes
  const pValue = p !== undefined ? spacing(p) : undefined;
  const paddingTop = py !== undefined ? spacing(py) : pValue;
  const paddingBottom = py !== undefined ? spacing(py) : pValue;
  const paddingLeft = px !== undefined ? spacing(px) : pValue;
  const paddingRight = px !== undefined ? spacing(px) : pValue;

  // Calculate margin values - individual props override my/mx for their respective axes
  const mValue = m !== undefined ? spacing(m) : undefined;
  const myValue = my !== undefined ? spacing(my) : mValue;
  const mxValue = mx !== undefined ? spacing(mx) : mValue;

  const computedStyle = {
    display,
    alignItems,
    justifyContent,
    gap: gap !== undefined ? spacing(gap) : undefined,
    marginTop: mt !== undefined ? spacing(mt) : myValue,
    marginBottom: mb !== undefined ? spacing(mb) : myValue,
    marginLeft: mxValue,
    marginRight: mxValue,
    // Use only longhand padding properties to avoid React warnings
    paddingTop,
    paddingBottom,
    paddingLeft,
    paddingRight,
    maxWidth,
    textAlign,
    ...sx,
    ...style
  };

  // Remove undefined values to avoid setting unnecessary styles
  Object.keys(computedStyle).forEach(key => {
    if (computedStyle[key] === undefined) {
      delete computedStyle[key];
    }
  });

  return <div ref={ref} style={computedStyle} {...props}>{children}</div>;
});


Box.displayName = 'macOS Box';

export default Box;


