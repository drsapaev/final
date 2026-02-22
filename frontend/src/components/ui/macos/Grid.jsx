import React from 'react';
import PropTypes from 'prop-types';
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
}, ref) => {void
  useTheme();
  void sm;
  void md;
  void lg;
  void xl;

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
          return `${size / 12 * 100}%`;
        }
        if (typeof size === 'boolean') {
          return 'auto';
        }
        return 'auto';
      };

      const getMaxWidth = (size) => {
        if (typeof size === 'number') {
          return `${size / 12 * 100}%`;
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
      {...props}>
      
      {children}
    </div>);

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
      {...props}>
      
      {children}
    </Grid>);

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
      {...props}>
      
      {children}
    </Grid>);

});

Grid.displayName = 'Grid';
GridContainer.displayName = 'GridContainer';
GridItem.displayName = 'GridItem';

Grid.propTypes = {
  children: PropTypes.node,
  className: PropTypes.string,
  style: PropTypes.object,
  container: PropTypes.bool,
  item: PropTypes.bool,
  xs: PropTypes.oneOfType([PropTypes.number, PropTypes.bool, PropTypes.string]),
  sm: PropTypes.oneOfType([PropTypes.number, PropTypes.bool, PropTypes.string]),
  md: PropTypes.oneOfType([PropTypes.number, PropTypes.bool, PropTypes.string]),
  lg: PropTypes.oneOfType([PropTypes.number, PropTypes.bool, PropTypes.string]),
  xl: PropTypes.oneOfType([PropTypes.number, PropTypes.bool, PropTypes.string]),
  spacing: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  direction: PropTypes.string,
  justify: PropTypes.string,
  alignItems: PropTypes.string,
  wrap: PropTypes.string
};

GridContainer.propTypes = {
  children: PropTypes.node,
  className: PropTypes.string,
  style: PropTypes.object,
  spacing: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  direction: PropTypes.string,
  justify: PropTypes.string,
  alignItems: PropTypes.string,
  wrap: PropTypes.string
};

GridItem.propTypes = {
  children: PropTypes.node,
  className: PropTypes.string,
  style: PropTypes.object,
  xs: PropTypes.oneOfType([PropTypes.number, PropTypes.bool, PropTypes.string]),
  sm: PropTypes.oneOfType([PropTypes.number, PropTypes.bool, PropTypes.string]),
  md: PropTypes.oneOfType([PropTypes.number, PropTypes.bool, PropTypes.string]),
  lg: PropTypes.oneOfType([PropTypes.number, PropTypes.bool, PropTypes.string]),
  xl: PropTypes.oneOfType([PropTypes.number, PropTypes.bool, PropTypes.string])
};

export default Grid;
export { GridContainer, GridItem };
