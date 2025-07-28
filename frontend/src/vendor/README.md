# Vendor Directory

This directory contains third-party libraries that have been copied locally for full control and customization.

## Why Vendor External Dependencies?

1. **Full Control**: Modify source code directly without affecting node_modules
2. **Version Stability**: Lock specific versions independent of npm updates  
3. **Custom Builds**: Remove unused features, optimize bundle size
4. **License Compliance**: Keep all license files with the code
5. **Security**: Audit and control all external code

## Current Vendored Libraries

### FormIO.js v4.21.7
- **Path**: `./formiojs/`
- **License**: MIT (see `./formiojs/package.json`)
- **Source**: https://github.com/formio/formio.js
- **Reason**: Full control over form builder functionality, remove Bootstrap conflicts with Tailwind
- **Last Updated**: 2025-01-28

## Usage

Import from vendor directory instead of node_modules:

```typescript
// Before
import { FormBuilder } from 'formiojs';

// After  
import { FormBuilder } from '@/vendor/formiojs';
```

## Maintenance

When updating vendored libraries:
1. Document version and date in this README
2. Preserve any custom modifications 
3. Update license information
4. Test all functionality after updates
5. Update TypeScript path mappings if needed