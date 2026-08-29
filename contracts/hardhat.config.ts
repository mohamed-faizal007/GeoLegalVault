import * as path from "path";

import "@nomicfoundation/hardhat-toolbox";
import * as dotenv from "dotenv";
import type { HardhatUserConfig } from "hardhat/config";

// Single source of truth: the repo-root .env (gitignored). Never a separate
// contracts/.env, never a hardcoded key (Guardrail #2).
dotenv.config({ path: path.resolve(__dirname, "..", ".env") });

const SEPOLIA_RPC_URL = process.env.SEPOLIA_RPC_URL ?? "";
const SERVICE_WALLET_PRIVATE_KEY = process.env.SERVICE_WALLET_PRIVATE_KEY ?? "";

function isPlaceholder(value: string): boolean {
  return !value || value.toUpperCase().includes("CHANGE_ME");
}

function normalizedKey(value: string): string {
  return value.startsWith("0x") ? value : `0x${value}`;
}

const config: HardhatUserConfig = {
  solidity: {
    version: "0.8.20",
    settings: {
      optimizer: { enabled: true, runs: 200 },
    },
  },
  networks: {
    // Only wired up with real credentials once you've set them in the
    // root .env — `npx hardhat test` never touches this, it runs against
    // Hardhat's own in-memory network with auto-funded test accounts.
    sepolia: {
      url: isPlaceholder(SEPOLIA_RPC_URL) ? "https://rpc.sepolia.org" : SEPOLIA_RPC_URL,
      accounts: isPlaceholder(SERVICE_WALLET_PRIVATE_KEY)
        ? []
        : [normalizedKey(SERVICE_WALLET_PRIVATE_KEY)],
      chainId: 11155111,
    },
  },
};

export default config;
