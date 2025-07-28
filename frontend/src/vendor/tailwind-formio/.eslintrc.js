module.exports = {
  extends: [require.resolve("@tsed/config/eslint/node")],
  rules: {
    "import/no-anonymous-default-export": 0,
    "jsx-a11y/anchor-is-valid": 0
  }
};
