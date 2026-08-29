import { ethers } from "hardhat";

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log(`Deploying DocumentAnchor with account: ${deployer.address}`);

  const balance = await ethers.provider.getBalance(deployer.address);
  console.log(`Account balance: ${ethers.formatEther(balance)} ETH`);

  const DocumentAnchor = await ethers.getContractFactory("DocumentAnchor");
  const contract = await DocumentAnchor.deploy();
  await contract.waitForDeployment();

  const address = await contract.getAddress();
  console.log(`DocumentAnchor deployed to: ${address}`);
  console.log("Paste this address into CONTRACT_ADDRESS in your .env file.");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
