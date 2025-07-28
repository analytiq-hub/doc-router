module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  testMatch: [
    '<rootDir>/ui/**/*.test.{js,ts}',
    '<rootDir>/e2e/**/*.test.{js,ts}'
  ],
  testTimeout: 30000,
  setupFilesAfterEnv: ['<rootDir>/setup.ts'],
  collectCoverageFrom: [
    '**/*.{js,ts}',
    '!**/*.d.ts',
    '!setup.ts'
  ],
  coverageDirectory: 'coverage/ui',
  transform: {
    '^.+\\.ts$': ['ts-jest', {
      tsconfig: 'tsconfig.json'
    }]
  }
};