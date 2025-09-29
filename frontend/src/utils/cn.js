// Small, dependency-free classNames combiner.
// Supports strings, arrays, and object maps { className: truthy }.

function cnInternal(...inputs) {
  const classes = [];

  const add = (value) => {
    if (!value) return;
    if (typeof value === "string") {
      classes.push(value);
      return;
    }
    if (Array.isArray(value)) {
      for (const item of value) add(item);
      return;
    }
    if (typeof value === "object") {
      for (const key in value) {
        if (Object.prototype.hasOwnProperty.call(value, key) && value[key]) {
          classes.push(key);
        }
      }
    }
  };

  for (const input of inputs) add(input);
  return classes.join(" ").trim();
}

export function cn(...inputs) {
  return cnInternal(...inputs);
}

export default cnInternal;


