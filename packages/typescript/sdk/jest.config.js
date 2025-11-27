module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  roots: ['<rootDir>/src', '<rootDir>/tests'],
  testMatch: ['**/__tests__/**/*.test.ts', '**/tests/**/*.test.ts'],
  transform: {
    '^.+\\.ts$': 'ts-jest',
  },
  // Global setup/teardown for integration tests (runs once for all workers)
  globalSetup: process.env.TEST_TYPE === 'integration' ? '<rootDir>/tests/setup/global-setup.ts' : undefined,
  globalTeardown: process.env.TEST_TYPE === 'integration' ? '<rootDir>/tests/setup/global-teardown.ts' : undefined,
  // Setup file runs in each worker to configure environment variables
  setupFilesAfterEnv: process.env.TEST_TYPE === 'integration' ? ['<rootDir>/tests/setup/jest-setup.ts'] : [],
  collectCoverageFrom: [
    'src/**/*.ts',
    '!src/**/*.d.ts',
    '!src/__tests__/**',
    '!tests/**',
  ],
  coverageDirectory: 'coverage',
  coverageReporters: ['text', 'lcov', 'html'],
  testTimeout: process.env.TEST_TYPE === 'integration' ? 60000 : 5000, // 60s for integration, 5s for unit
  // All tests can run in parallel using all CPU cores
  maxWorkers: '100%',
  // Force exit for integration tests to avoid 1s delay waiting for handles to close
  ...(process.env.TEST_TYPE === 'integration' && { forceExit: true })
};
