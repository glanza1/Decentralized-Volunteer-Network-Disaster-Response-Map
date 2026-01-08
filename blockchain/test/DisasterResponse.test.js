/**
 * DisasterResponse.test.js - Tests for all disaster response contracts
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("Disaster Response Contracts", function () {
    let volunteerIdentity, taskEscrow, aidDistribution, meshIncentive;
    let owner, user1, user2, user3, volunteer1, volunteer2;

    beforeEach(async function () {
        [owner, user1, user2, user3, volunteer1, volunteer2] = await ethers.getSigners();

        // Deploy VolunteerIdentity
        const VolunteerIdentity = await ethers.getContractFactory("VolunteerIdentity");
        volunteerIdentity = await VolunteerIdentity.deploy();

        // Deploy MeshIncentive
        const MeshIncentive = await ethers.getContractFactory("MeshIncentive");
        meshIncentive = await MeshIncentive.deploy();

        // Deploy TaskEscrow
        const TaskEscrow = await ethers.getContractFactory("TaskEscrow");
        taskEscrow = await TaskEscrow.deploy(await volunteerIdentity.getAddress());

        // Deploy AidDistribution
        const AidDistribution = await ethers.getContractFactory("AidDistribution");
        aidDistribution = await AidDistribution.deploy(
            await taskEscrow.getAddress(),
            await volunteerIdentity.getAddress()
        );

        // Authorize TaskEscrow to update VolunteerIdentity
        await volunteerIdentity.setAuthorizedContract(await taskEscrow.getAddress(), true);
    });

    // ===== VolunteerIdentity Tests =====
    describe("VolunteerIdentity", function () {
        it("Should register a new volunteer", async function () {
            await volunteerIdentity.connect(user1).register("ipfs://QmTest");

            const identity = await volunteerIdentity.getIdentity(user1.address);
            expect(identity.tokenId).to.equal(1n);
            expect(identity.reputationScore).to.equal(100n); // Starting score
        });

        it("Should prevent duplicate registration", async function () {
            await volunteerIdentity.connect(user1).register("ipfs://QmTest");
            await expect(
                volunteerIdentity.connect(user1).register("ipfs://QmTest2")
            ).to.be.revertedWith("Already registered");
        });

        it("Should return correct trust levels", async function () {
            await volunteerIdentity.connect(user1).register("ipfs://QmTest");

            // Starting score is 100, which is trust level 1
            expect(await volunteerIdentity.getTrustLevel(user1.address)).to.equal(1);

            // Authorize owner to update reputation
            await volunteerIdentity.setAuthorizedContract(owner.address, true);

            // Increase to level 2 (200+)
            await volunteerIdentity.updateReputation(user1.address, 100);
            expect(await volunteerIdentity.getTrustLevel(user1.address)).to.equal(2);

            // Increase to level 3 (500+)
            await volunteerIdentity.updateReputation(user1.address, 300);
            expect(await volunteerIdentity.getTrustLevel(user1.address)).to.equal(3);

            // Increase to level 4 (800+)
            await volunteerIdentity.updateReputation(user1.address, 300);
            expect(await volunteerIdentity.getTrustLevel(user1.address)).to.equal(4);
        });

        it("Should prevent SBT transfer", async function () {
            await volunteerIdentity.connect(user1).register("ipfs://QmTest");

            await expect(
                volunteerIdentity.connect(user1).transferFrom(user1.address, user2.address, 1)
            ).to.be.revertedWith("Soul-bound: transfer disabled");
        });
    });

    // ===== TaskEscrow Tests =====
    describe("TaskEscrow", function () {
        const taskId = ethers.keccak256(ethers.toUtf8Bytes("test-task-123"));

        beforeEach(async function () {
            // Register all users
            await volunteerIdentity.connect(user1).register("ipfs://user1");
            await volunteerIdentity.connect(volunteer1).register("ipfs://vol1");
            await volunteerIdentity.connect(volunteer2).register("ipfs://vol2");

            // Boost volunteer trust levels to allow verification
            await volunteerIdentity.setAuthorizedContract(owner.address, true);
            await volunteerIdentity.updateReputation(volunteer1.address, 400); // Level 3
            await volunteerIdentity.updateReputation(volunteer2.address, 400); // Level 3
        });

        it("Should create a task", async function () {
            await taskEscrow.connect(user1).createTask(
                taskId,
                41000000n, // latitude * 1e6
                29000000n, // longitude * 1e6
                "medical",
                "critical",
                "ipfs://QmTaskContent",
                3600 // 1 hour TTL
            );

            expect(await taskEscrow.taskExists(taskId)).to.be.true;
        });

        it("Should verify a task", async function () {
            // Create task
            await taskEscrow.connect(user1).createTask(
                taskId, 41000000n, 29000000n, "medical", "high",
                "ipfs://QmTask", 3600
            );

            // Verify (need enough trust to reach threshold of 10)
            await taskEscrow.connect(volunteer1).verifyTask(taskId);
            await taskEscrow.connect(volunteer2).verifyTask(taskId);

            // Check status (with 2 level-3 verifiers, score = 6, may need more)
            const trustInfo = await taskEscrow.getTaskTrustInfo(taskId);
            expect(trustInfo.verificationScore).to.be.greaterThan(0n);
        });

        it("Should complete the full task lifecycle", async function () {
            // Create task
            await taskEscrow.connect(user1).createTask(
                taskId, 41000000n, 29000000n, "medical", "critical",
                "ipfs://QmTask", 3600
            );

            // Verify (boost both volunteers to level 4 to get score > 10)
            await volunteerIdentity.updateReputation(volunteer1.address, 400); // Now 800+
            await volunteerIdentity.updateReputation(volunteer2.address, 400); // Now 800+

            await taskEscrow.connect(volunteer1).verifyTask(taskId);
            await taskEscrow.connect(volunteer2).verifyTask(taskId); // Total score = 8

            // Still need more verification - add a third verifier
            await volunteerIdentity.connect(user3).register("ipfs://user3");
            await volunteerIdentity.updateReputation(user3.address, 400);
            await taskEscrow.connect(user3).verifyTask(taskId); // Total score = 12

            // Accept task
            await taskEscrow.connect(volunteer1).acceptTask(taskId);

            // Complete task (only creator can complete)
            await taskEscrow.connect(user1).completeTask(taskId);

            const trustInfo = await taskEscrow.getTaskTrustInfo(taskId);
            expect(trustInfo.isVerified).to.be.true;
            expect(trustInfo.status).to.equal(3n); // COMPLETED status
        });
    });

    // ===== MeshIncentive Tests =====
    describe("MeshIncentive", function () {
        it("Should reward packet relay", async function () {
            await meshIncentive.recordRelay(user1.address, 5);

            const balance = await meshIncentive.balanceOf(user1.address);
            expect(balance).to.equal(ethers.parseEther("5")); // 5 tokens for 5 packets
        });

        it("Should reward uptime", async function () {
            await meshIncentive.recordUptime(user1.address, 120); // 2 hours

            const balance = await meshIncentive.balanceOf(user1.address);
            expect(balance).to.equal(ethers.parseEther("20")); // 10 per hour * 2
        });

        it("Should track node stats", async function () {
            await meshIncentive.recordRelay(user1.address, 10);
            await meshIncentive.recordUptime(user1.address, 60);
            await meshIncentive.recordDelivery(user1.address, ethers.keccak256(ethers.toUtf8Bytes("msg1")));

            const stats = await meshIncentive.getNodeStats(user1.address);
            expect(stats.packetsRelayed).to.equal(10n);
            expect(stats.uptimeMinutes).to.equal(60n);
            expect(stats.messagesDelivered).to.equal(1n);
        });
    });

    // ===== AidDistribution Tests =====
    describe("AidDistribution", function () {
        const taskId = ethers.keccak256(ethers.toUtf8Bytes("donation-task"));

        beforeEach(async function () {
            // Setup users and task
            await volunteerIdentity.connect(user1).register("ipfs://user1");
            await volunteerIdentity.connect(volunteer1).register("ipfs://vol1");
            await volunteerIdentity.connect(volunteer2).register("ipfs://vol2");
            await volunteerIdentity.connect(user2).register("ipfs://user2");
            await volunteerIdentity.connect(user3).register("ipfs://user3");

            // Boost trust levels
            await volunteerIdentity.setAuthorizedContract(owner.address, true);
            await volunteerIdentity.updateReputation(volunteer1.address, 700); // Level 4
            await volunteerIdentity.updateReputation(volunteer2.address, 700); // Level 4
            await volunteerIdentity.updateReputation(user2.address, 700); // Level 4
            await volunteerIdentity.updateReputation(user3.address, 700); // Level 4

            // Create and verify task
            await taskEscrow.connect(user1).createTask(
                taskId, 41000000n, 29000000n, "rescue", "critical",
                "ipfs://QmTask", 3600
            );
            await taskEscrow.connect(volunteer1).verifyTask(taskId);
            await taskEscrow.connect(volunteer2).verifyTask(taskId);
            await taskEscrow.connect(user2).verifyTask(taskId); // Now verified (score >= 10)
        });

        it("Should accept donations", async function () {
            await aidDistribution.connect(user2).donate(taskId, {
                value: ethers.parseEther("1")
            });

            const status = await aidDistribution.getPoolStatus(taskId);
            expect(status.totalAmount).to.equal(ethers.parseEther("1"));
        });

        it("Should collect signatures from trusted users", async function () {
            // Donate first
            await aidDistribution.connect(owner).donate(taskId, {
                value: ethers.parseEther("1")
            });

            // Sign (need trust level 3+)
            await aidDistribution.connect(volunteer1).signRelease(taskId);
            await aidDistribution.connect(volunteer2).signRelease(taskId);
            await aidDistribution.connect(user2).signRelease(taskId);

            const status = await aidDistribution.getPoolStatus(taskId);
            expect(status.signatureCount).to.equal(3n);
        });
    });
});
