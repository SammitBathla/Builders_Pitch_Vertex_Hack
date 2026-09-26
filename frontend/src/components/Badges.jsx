import React from "react";
import { CATEGORY_ICON } from "../format.js";

export function CategoryBadge({ category }) {
  return (
    <span className={`badge category-${category}`}>
      {CATEGORY_ICON[category] || "● "}
      {category}
    </span>
  );
}

export function SourceBadge({ source }) {
  if (source === "override") {
    return <span className="badge badge-override">{"✎"} Human override</span>;
  }
  return <span className="badge badge-rule">{"⚙"} Rule-derived</span>;
}

export function StatusBadge({ status, signedOffBy }) {
  if (status === "signed_off") {
    return <span className="badge badge-ok">{"✓"} Signed off{signedOffBy ? ` by ${signedOffBy}` : ""}</span>;
  }
  return <span className="badge badge-unknown">{"⌛"} In progress</span>;
}
