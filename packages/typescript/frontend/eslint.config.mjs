import nextConfig from 'eslint-config-next/core-web-vitals';
import tsConfig from 'eslint-config-next/typescript';

export default [
  ...nextConfig,
  ...tsConfig,
  {
    // Downgrade new strict rules that flag pre-existing patterns
    rules: {
      // setState in useEffect is a common pattern for SSR hydration and data fetching
      'react-hooks/set-state-in-effect': 'warn',
    },
  },
];
