import { spawn, ChildProcess, exec } from 'child_process';
import { setTimeout } from 'timers/promises';
import * as path from 'path';
import * as fs from 'fs';

export interface TestServerConfig {
  port: number;
  mongodbUri: string;
  env: string;
  nextauthSecret: string;
}

export class TestServer {
  private process: ChildProcess | null = null;
  private config: TestServerConfig;
  private baseUrl: string;
  private signalHandler: (() => void) | null = null;

  constructor(config: TestServerConfig) {
    this.config = config;
    this.baseUrl = `http://localhost:${config.port}`;
  }

  async start(): Promise<void> {
    if (this.process) {
      throw new Error('Test server is already running');
    }

    // Kill any existing uvicorn processes on this port before starting
    await this.killExistingUvicornProcesses();

    // Set up signal handler for graceful shutdown on Ctrl-C
    this.setupSignalHandlers();

    const packagesDir = path.join(__dirname, '../../../../python'); // Go up to packages directory
    const sdkDir = path.join(__dirname, '../..'); // docrouter_ts_sdk directory
    const venvPython = path.join(sdkDir, '.venv/bin/python');

    // Check if virtual environment exists, if not create it
    await this.ensureVenv(sdkDir, packagesDir);

    // Start the FastAPI server using the virtual environment
    // The server needs to run from the packages directory where app is located
    const uvicornArgs = [
      '-m', 'uvicorn',
      'app.main:app',
      '--host', '0.0.0.0',
      '--port', this.config.port.toString(),
      '--reload'
    ];
    
    console.log('Starting uvicorn with:');
    console.log('Python executable:', venvPython);
    console.log('Args:', uvicornArgs);
    console.log('Working directory:', packagesDir);
    
    this.process = spawn(venvPython, uvicornArgs, {
      env: process.env,
      stdio: ['ignore', 'pipe', 'pipe'],
      cwd: packagesDir // This should be the packages directory
    });

    // Capture server logs for debugging
    this.process.stdout?.on('data', (_data) => {
      // console.log('Server stdout:', data.toString());
    });
    this.process.stderr?.on('data', (_data) => {
      // console.log('Server stderr:', data.toString());
    });

    this.process.on('error', (error) => {
      console.error(`Server process error: ${error.message}`);
    });

    this.process.on('exit', () => {
      // Server exited - suppress log
    });

    // Wait for server to start
    await this.waitForServer();
  }

  async stop(): Promise<void> {
    // Clean up signal handlers
    this.cleanupSignalHandlers();
    
    if (this.process) {
      this.process.kill('SIGTERM');
      await new Promise<void>((resolve) => {
        if (this.process) {
          this.process.on('exit', () => resolve());
        }
        // Force kill after 5 seconds
        setTimeout(5000).then(() => {
          if (this.process && !this.process.killed) {
            this.process.kill('SIGKILL');
            resolve();
          }
        });
      });
      this.process = null;
    }
  }

  getBaseUrl(): string {
    return this.baseUrl;
  }

  private async killExistingUvicornProcesses(): Promise<void> {
    console.log(`Killing any existing uvicorn processes on port ${this.config.port}...`);
    
    try {
      // Kill processes by uvicorn command pattern - use execCommandSilent to avoid errors
      await this.execCommandSilent(`pkill -f "uvicorn.*${this.config.port}"`);
      
      // Also kill any processes using the specific port
      await this.execCommandSilent(`lsof -ti:${this.config.port} | xargs -r kill -9`);
      
      // Give a small delay to ensure processes are killed
      await setTimeout(1000);
      
      console.log('Existing uvicorn processes killed (if any)');
    } catch (error) {
      // Silently ignore errors - this is just cleanup
    }
  }

  private setupSignalHandlers(): void {
    this.signalHandler = async () => {
      console.log('\nReceived SIGINT (Ctrl-C), cleaning up uvicorn processes...');
      await this.killExistingUvicornProcesses();
      process.exit(0);
    };
    
    process.on('SIGINT', this.signalHandler);
  }

  private cleanupSignalHandlers(): void {
    if (this.signalHandler) {
      process.removeListener('SIGINT', this.signalHandler);
      this.signalHandler = null;
    }
  }

  private async ensureVenv(sdkDir: string, packagesDir: string): Promise<void> {
    const venvDir = path.join(sdkDir, '.venv');

    // Remove existing virtual environment if it exists
    if (fs.existsSync(venvDir)) {
      console.log('Removing existing virtual environment...');
      fs.rmSync(venvDir, { recursive: true, force: true });
    }

    console.log('Creating virtual environment...');
    // Create virtual environment in docrouter_ts_sdk directory
    // Try python3.11 first, then fallback to python3.9, then python3
    const pythonVersions = ['python3.13', 'python3.11', 'python3.9', 'python3'];
    let venvCreated = false;
    
    for (const pythonCmd of pythonVersions) {
      try {
        console.log(`Trying to create venv with ${pythonCmd}...`);
        await this.execCommand(`${pythonCmd} -m venv .venv`, sdkDir);
        venvCreated = true;
        console.log(`Successfully created venv with ${pythonCmd}`);
        break;
      } catch (error) {
        console.log(`${pythonCmd} not available, trying next version...`);
        continue;
      }
    }
    
    if (!venvCreated) {
      throw new Error('No suitable Python version found. Tried: python3.11, python3.9, python3');
    }

    // Install requirements from packages directory using uv pip install with virtual environment
    console.log('Installing Python dependencies...');
    const venvPython = path.join(sdkDir, '.venv/bin/python');
    await this.execCommand(`uv pip install --python ${venvPython} -r ${path.join(packagesDir, 'requirements.txt')}`, packagesDir);
  }

  private async execCommand(command: string, cwd: string): Promise<void> {
    return new Promise((resolve, reject) => {
      exec(command, { cwd }, (error, stdout, stderr) => {
        if (error) {
          console.error(`Command failed: ${command}`);
          console.error(`Error: ${error.message}`);
          console.error(`Stderr: ${stderr}`);
          reject(error);
        } else {
          console.log(`Command succeeded: ${command}`);
          if (stdout) console.log(`Stdout: ${stdout}`);
          resolve();
        }
      });
    });
  }

  private async execCommandSilent(command: string, cwd: string = process.cwd()): Promise<void> {
    return new Promise((resolve) => {
      exec(command, { cwd }, (_error, _stdout, _stderr) => {
        // Silently resolve regardless of success or failure
        resolve();
      });
    });
  }

  private async waitForServer(maxRetries = 60): Promise<void> {
    // Give the server a bit more time to initialize before first check
    await setTimeout(2000);

    for (let i = 0; i < maxRetries; i++) {
      try {
        // Try to connect to the server (any endpoint will do)
        const response = await fetch(`${this.baseUrl}/docs`);
        if (response.status === 200 || response.status === 404) {
          // Server is responding, now wait for admin user to be created
          await this.waitForAdminUser();
          return;
        }
      } catch (error) {
        // Server not ready yet - only log every 5 attempts to reduce noise
        if (i % 5 === 0) {
          console.log(`Waiting for server... (${i + 1}/${maxRetries})`);
        }
      }
      await setTimeout(500);
    }
    throw new Error(`Test server failed to start after ${maxRetries * 0.5} seconds`);
  }

  private async waitForAdminUser(maxRetries = 30): Promise<void> {
    const { MongoClient } = await import('mongodb');
    const client = new MongoClient(this.config.mongodbUri);

    try {
      await client.connect();
      const db = client.db(this.config.env);
      const adminEmail = process.env.ADMIN_EMAIL || 'test-admin@example.com';

      for (let i = 0; i < maxRetries; i++) {
        const adminUser = await db.collection('users').findOne({ email: adminEmail });
        if (adminUser) {
          console.log('Admin user created successfully');
          return;
        }

        if (i % 5 === 0 && i > 0) {
          console.log(`Waiting for admin user... (${i + 1}/${maxRetries})`);
        }
        await setTimeout(500);
      }

      throw new Error(`Admin user not created after ${maxRetries * 0.5} seconds`);
    } finally {
      await client.close();
    }
  }
}

// Default test server configuration
export const defaultTestConfig: TestServerConfig = {
  port: 8001, // Use different port from main app
  mongodbUri: 'mongodb://localhost:27017',
  env: 'pytest_ts', // Use dedicated database for TypeScript SDK tests
  nextauthSecret: 'test_secret_key_for_tests'
};
