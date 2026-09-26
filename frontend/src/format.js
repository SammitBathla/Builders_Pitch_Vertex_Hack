export function fmtNum(n, digits = 2) {
  if (n === null || n === undefined) return "—";
  return Number(n).toFixed(digits);
}

export function fmtDate(s) {
  return (s || "").slice(0, 19).replace("T", " ");
}

export const CATEGORY_ICON = {
  Certain: "✓ ",
  Probable: "✓ ",
  Possible: "● ",
  Unlikely: "✗ ",
  Unassessable: "? ",
};

export function categoryBadgeProps(category) {
  return {
    className: `badge category-${category}`,
    icon: CATEGORY_ICON[category] || "● ",
  };
}
