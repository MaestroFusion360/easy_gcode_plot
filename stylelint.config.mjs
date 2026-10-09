export default {
  extends: ["stylelint-config-recommended"],
  // Component-scoped selectors do not share elements. Reordering unrelated
  // sections by specificity would change the established cascade and layout.
  rules: { "no-descending-specificity": null },
};
