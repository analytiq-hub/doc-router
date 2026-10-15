// Puppeteer 24+ is ESM-only. Jest can require() it only when Node's VM
// module API is enabled, which still needs --experimental-vm-modules
// (set on the npm scripts). On Node 24.9+ that API exists, but it is not
// exposed unless the flag is on, so Jest otherwise fails with ERR_REQUIRE_ESM.
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