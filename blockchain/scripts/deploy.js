/**
 * deploy.js - Deploy all disaster response smart contracts
 * 
 * Deploy order is important due to contract dependencies:
 * 1. VolunteerIdentity (no dependencies)
 * 2. MeshIncentive (no dependencies)
 * 3. TaskEscrow (depends on VolunteerIdentity)
 * 4. AidDistribution (depends on TaskEscrow, VolunteerIdentity)
 */

const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
    console.log("🚀 Starting deployment of Disaster Response contracts...\n");

    const [deployer] = await hre.ethers.getSigners();
    console.log("Deploying contracts with account:", deployer.address);
    console.log("Account balance:", (await hre.ethers.provider.getBalance(deployer.address)).toString());
    console.log();

    // Store deployment info
    const deployments = {};

    // ===== 1. Deploy VolunteerIdentity =====
    console.log("📋 Deploying VolunteerIdentity (Soul-Bound NFT)...");
    const VolunteerIdentity = await hre.ethers.getContractFactory("VolunteerIdentity");
    const volunteerIdentity = await VolunteerIdentity.deploy();
    await volunteerIdentity.waitForDeployment();
    const volunteerIdentityAddress = await volunteerIdentity.getAddress();
    console.log("✅ VolunteerIdentity deployed to:", volunteerIdentityAddress);

    deployments.VolunteerIdentity = {
        address: volunteerIdentityAddress,
        abi: VolunteerIdentity.interface.formatJson()
    };

    // ===== 2. Deploy MeshIncentive =====
    console.log("\n🔗 Deploying MeshIncentive (P2P Rewards Token)...");
    const MeshIncentive = await hre.ethers.getContractFactory("MeshIncentive");
    const meshIncentive = await MeshIncentive.deploy();
    await meshIncentive.waitForDeployment();
    const meshIncentiveAddress = await meshIncentive.getAddress();
    console.log("✅ MeshIncentive deployed to:", meshIncentiveAddress);

    deployments.MeshIncentive = {
        address: meshIncentiveAddress,
        abi: MeshIncentive.interface.formatJson()
    };

    // ===== 3. Deploy TaskEscrow =====
    console.log("\n📝 Deploying TaskEscrow (Task Lifecycle)...");
    const TaskEscrow = await hre.ethers.getContractFactory("TaskEscrow");
    const taskEscrow = await TaskEscrow.deploy(volunteerIdentityAddress);
    await taskEscrow.waitForDeployment();
    const taskEscrowAddress = await taskEscrow.getAddress();
    console.log("✅ TaskEscrow deployed to:", taskEscrowAddress);

    deployments.TaskEscrow = {
        address: taskEscrowAddress,
        abi: TaskEscrow.interface.formatJson()
    };

    // ===== 4. Deploy AidDistribution =====
    console.log("\n💰 Deploying AidDistribution (Multi-Sig Donations)...");
    const AidDistribution = await hre.ethers.getContractFactory("AidDistribution");
    const aidDistribution = await AidDistribution.deploy(
        taskEscrowAddress,
        volunteerIdentityAddress
    );
    await aidDistribution.waitForDeployment();
    const aidDistributionAddress = await aidDistribution.getAddress();
    console.log("✅ AidDistribution deployed to:", aidDistributionAddress);

    deployments.AidDistribution = {
        address: aidDistributionAddress,
        abi: AidDistribution.interface.formatJson()
    };

    // ===== Configure Contract Permissions =====
    console.log("\n🔐 Configuring contract permissions...");

    // Authorize TaskEscrow to update VolunteerIdentity
    await volunteerIdentity.setAuthorizedContract(taskEscrowAddress, true);
    console.log("  - TaskEscrow authorized on VolunteerIdentity");

    // Authorize AidDistribution (optional, for future features)
    await volunteerIdentity.setAuthorizedContract(aidDistributionAddress, true);
    console.log("  - AidDistribution authorized on VolunteerIdentity");

    // ===== Save Deployment Info =====
    const deploymentsDir = path.join(__dirname, "..", "deployments");
    if (!fs.existsSync(deploymentsDir)) {
        fs.mkdirSync(deploymentsDir, { recursive: true });
    }

    // Save individual contract info
    for (const [name, data] of Object.entries(deployments)) {
        const filePath = path.join(deploymentsDir, `${name}.json`);
        fs.writeFileSync(filePath, JSON.stringify(data, null, 2));
        console.log(`\n📁 Saved ${name} deployment to: ${filePath}`);
    }

    // Save combined deployment info
    const networkName = hre.network.name;
    const combinedPath = path.join(deploymentsDir, `${networkName}_deployments.json`);
    fs.writeFileSync(combinedPath, JSON.stringify({
        network: networkName,
        timestamp: new Date().toISOString(),
        deployer: deployer.address,
        contracts: Object.fromEntries(
            Object.entries(deployments).map(([name, data]) => [name, data.address])
        )
    }, null, 2));

    // ===== Summary =====
    console.log("\n" + "=".repeat(60));
    console.log("🎉 DEPLOYMENT COMPLETE!");
    console.log("=".repeat(60));
    console.log("\nContract Addresses:");
    console.log(`  VolunteerIdentity: ${volunteerIdentityAddress}`);
    console.log(`  MeshIncentive:     ${meshIncentiveAddress}`);
    console.log(`  TaskEscrow:        ${taskEscrowAddress}`);
    console.log(`  AidDistribution:   ${aidDistributionAddress}`);
    console.log("\nDeployment info saved to:", deploymentsDir);
    console.log("=".repeat(60));
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error("❌ Deployment failed:", error);
        process.exit(1);
    });
