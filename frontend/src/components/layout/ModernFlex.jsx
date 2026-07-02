import { useTheme } from '../../contexts/ThemeContext';
import PropTypes from 'prop-types';
import './ModernFlex.css';

const ModernFlex = ({
  children,
  direction = 'row',
  wrap = 'nowrap',
  justify = 'flex-start',
  align = 'stretch',
  gap = 'medium',
  responsive = true,
  className = '',
  ...props
}) => {void
  useTheme();

  const gapValues = {
    none: '0',
    small: '8px',
    medium: '16px',
    large: '24px',
    xl: '32px'
  };

  const flexStyles = {
    display: 'flex',
    flexDirection: direction,
    flexWrap: wrap,
    justifyContent: justify,
    alignItems: align,
    gap: gapValues[gap] || gap
  };

  return (
    <div
      className={`modern-flex ${responsive ? 'responsive' : ''} ${className}`}
      style={flexStyles}
      {...props}>
      
      {children}
    </div>);

};

// Компонент элемента flex
export const FlexItem = ({
  children,
  flex = 'auto',
  alignSelf = 'auto',
  order = 'auto',
  className = '',
  ...props
}) => {
  const itemStyles = {
    flex,
    alignSelf,
    order: order !== 'auto' ? order : undefined
  };

  return (
    <div
      className={`flex-item ${className}`}
      style={itemStyles}
      {...props}>
      
      {children}
    </div>);

};

ModernFlex.propTypes = {
  children: PropTypes.node,
  direction: PropTypes.string,
  wrap: PropTypes.string,
  justify: PropTypes.string,
  align: PropTypes.string,
  gap: PropTypes.oneOfType([
    PropTypes.oneOf(['none', 'small', 'medium', 'large', 'xl']),
    PropTypes.string,
    PropTypes.number
  ]),
  responsive: PropTypes.bool,
  className: PropTypes.string
};

FlexItem.propTypes = {
  children: PropTypes.node,
  flex: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  alignSelf: PropTypes.string,
  order: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  className: PropTypes.string
};

export default ModernFlex;
