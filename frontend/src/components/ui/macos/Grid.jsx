import React from 'react';
import { useTheme } from '../../../contexts/ThemeContext';

/**
 * macOS-style Grid Component
 * Implements Apple's Human Interface Guidelines for grid layouts
 */
const Grid = React.forwardRef(({
  children,
  className = '',
  style = {},
  container = false,
  item = false,
  xs,
  sm,
  md,
  lg,
  xl,
  spacing = 0,
  direction = 'row',
  justify = 'flex-start',
  alignItems = 'stretch',
  wrap = 'wrap',
  ...props
}, ref) => {
  const { theme } = useTheme();

  const getGridStyles = () => {
    if (container) {
      return {
        display: 'flex',
        flexDirection: direction,
        justifyContent: justify,
        alignItems: alignItems,
        flexWrap: wrap,
        gap: typeof spacing === 'number' ? `${spacing * 8}px` : spacing,
        ...style
      };
    }

    if (item) {
      const getFlexBasis = (size) => {
        if (typeof size === 'number') {
          return `${(size / 12) * 100}%`;
        }
        if (typeof size === 'boolean') {
          return 'auto';
        }
        return 'auto';
      };

      const getMaxWidth = (size) => {
        if (typeof size === 'number') {
          return `${(size / 12) * 100}%`;
        }
        return 'none';
      };

      return {
        flexBasis: getFlexBasis(xs),
        maxWidth: getMaxWidth(xs),
        flexGrow: typeof xs === 'number' ? 0 : 1,
        flexShrink: 0,
        ...style
      };
    }

    return style;
  };

  const gridStyles = getGridStyles();

  return (
    <div
      ref={ref}
      className={`mac-grid ${container ? 'mac-grid--container' : ''} ${item ? 'mac-grid--item' : ''} ${className}`}
      style={gridStyles}
      {...props}
    >
      {children}
    </div>
  );
});

/**
 * macOS-style GridContainer Component
 */
const GridContainer = React.forwardRef(({
  children,
  className = '',
  style = {},
  spacing = 2,
  direction = 'row',
  justify = 'flex-start',
  alignItems = 'stretch',
  wrap = 'wrap',
  ...props
}, ref) => {
  return (
    <Grid
      ref={ref}
      container
      spacing={spacing}
      direction={direction}
      justify={justify}
      alignItems={alignItems}
      wrap={wrap}
      className={className}
      style={style}
      {...props}
    >
      {children}
    </Grid>
  );
});

/**
 * macOS-style GridItem Component
 */
const GridItem = React.forwardRef(({
  children,
  className = '',
  style = {},
  xs,
  sm,
  md,
  lg,
  xl,
  ...props
}, ref) => {
  return (
    <Grid
      ref={ref}
      item
      xs={xs}
      sm={sm}
      md={md}
      lg={lg}
      xl={xl}
      className={className}
      style={style}
      {...props}
    >
      {children}
    </Grid>
  );
});

Grid.displayName = 'Grid';
GridContainer.displayName = 'GridContainer';
GridItem.displayName = 'GridItem';

export default Grid;
export { GridContainer, GridItem };
