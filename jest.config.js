module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  testMatch: [
    '<rootDir>/tests/ui/**/*.test.{js,ts}',
    '<rootDir>/tests/e2e/**/*.test.{js,ts}'
  ],
  testTimeout: 30000,
  setupFilesAfterEnv: ['<rootDir>/tests/setup.ts'],
  collectCoverageFrom: [
    'tests/**/*.{js,ts}',
    '!tests/**/*.d.ts',
    '!tests/setup.ts'
  ],
  coverageDirectory: 'coverage/ui',
  transform: {
    '^.+\\.ts$': ['ts-jest', {
      tsconfig: 'tests/tsconfig.json'
    }]
  }
};