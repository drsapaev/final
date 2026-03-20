# Searching for buttons without aria-labels or tooltips
find frontend/src/components -type f -name "*.jsx" -exec grep -Hn "<button" {} \; | grep -v "aria-label" | grep -v "title" | grep "className"
