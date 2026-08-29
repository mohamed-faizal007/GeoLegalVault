import { anyValue } from "@nomicfoundation/hardhat-chai-matchers/withArgs";
import { expect } from "chai";
import { ethers } from "hardhat";

describe("DocumentAnchor", () => {
  const documentId = "doc-100";
  const version = 1;
  const hash = ethers.keccak256(ethers.toUtf8Bytes("fake-sha256-of-v1"));
  const eventType = 1; // e.g. APPROVED

  async function deployFixture() {
    const [owner, otherWriter, stranger] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("DocumentAnchor");
    const contract = await Factory.deploy();
    await contract.waitForDeployment();
    return { contract, owner, otherWriter, stranger };
  }

  it("anchors a hash and getAnchor reads it back", async () => {
    const { contract } = await deployFixture();
    await contract.anchor(documentId, version, hash, eventType);

    const [storedHash, storedEventType, ts, exists] = await contract.getAnchor(
      documentId,
      version
    );
    expect(storedHash).to.equal(hash);
    expect(storedEventType).to.equal(eventType);
    expect(exists).to.equal(true);
    expect(ts).to.be.greaterThan(0n);
  });

  it("emits AnchorCreated on a successful anchor", async () => {
    const { contract } = await deployFixture();
    await expect(contract.anchor(documentId, version, hash, eventType))
      .to.emit(contract, "AnchorCreated")
      .withArgs(documentId, version, hash, eventType, anyValue);
  });

  it("returns exists=false for a never-anchored document+version", async () => {
    const { contract } = await deployFixture();
    const [storedHash, storedEventType, ts, exists] = await contract.getAnchor("nope", 99);
    expect(exists).to.equal(false);
    expect(storedHash).to.equal(ethers.ZeroHash);
    expect(storedEventType).to.equal(0);
    expect(ts).to.equal(0n);
  });

  it("reverts on re-anchoring the same document+version", async () => {
    const { contract } = await deployFixture();
    await contract.anchor(documentId, version, hash, eventType);

    await expect(contract.anchor(documentId, version, hash, eventType)).to.be.revertedWith(
      "already anchored"
    );
  });

  it("allows anchoring a different version of the same document", async () => {
    const { contract } = await deployFixture();
    await contract.anchor(documentId, 1, hash, eventType);
    await expect(contract.anchor(documentId, 2, hash, eventType)).to.not.be.reverted;
  });

  it("rejects anchoring from an account that is not a writer", async () => {
    const { contract, stranger } = await deployFixture();
    await expect(
      contract.connect(stranger).anchor(documentId, version, hash, eventType)
    ).to.be.revertedWith("not authorized");
  });

  it("allows anchoring once granted writer rights by the owner", async () => {
    const { contract, owner, otherWriter } = await deployFixture();
    await contract.connect(owner).setWriter(otherWriter.address, true);

    await expect(contract.connect(otherWriter).anchor(documentId, version, hash, eventType)).to
      .not.be.reverted;
  });

  it("revokes writer rights", async () => {
    const { contract, owner, otherWriter } = await deployFixture();
    await contract.connect(owner).setWriter(otherWriter.address, true);
    await contract.connect(owner).setWriter(otherWriter.address, false);

    await expect(
      contract.connect(otherWriter).anchor(documentId, version, hash, eventType)
    ).to.be.revertedWith("not authorized");
  });

  it("only the owner can call setWriter", async () => {
    const { contract, stranger, otherWriter } = await deployFixture();
    await expect(
      contract.connect(stranger).setWriter(otherWriter.address, true)
    ).to.be.revertedWith("only owner");
  });
});
