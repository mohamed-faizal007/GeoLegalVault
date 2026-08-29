// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title DocumentAnchor
/// @notice Anchors a document version's SHA-256 hash + lifecycle event on
/// chain. Only the hash and small metadata are stored here — never file
/// bytes, filenames, or any PII (Guardrail #1). No upgradeability, no
/// tokens, no complex roles — deliberately minimal (Plan Part 12).
contract DocumentAnchor {
    address public owner; // backend service wallet that deployed this contract
    mapping(address => bool) public writers; // accounts allowed to anchor

    struct Anchor {
        bytes32 hash;
        uint32 version;
        uint8 eventType;
        uint64 ts;
        bool exists;
    }

    // key = keccak256(documentId, version)
    mapping(bytes32 => Anchor) private anchors;

    event AnchorCreated(
        string documentId,
        uint32 version,
        bytes32 hash,
        uint8 eventType,
        uint64 ts
    );

    modifier onlyWriter() {
        require(writers[msg.sender], "not authorized");
        _;
    }

    constructor() {
        owner = msg.sender;
        writers[msg.sender] = true;
    }

    /// @notice Grant or revoke writer (anchoring) rights. Owner only.
    function setWriter(address account, bool allowed) external {
        require(msg.sender == owner, "only owner");
        writers[account] = allowed;
    }

    /// @notice Anchor a document version's hash. Reverts if this exact
    /// (documentId, version) pair was already anchored — one immutable
    /// record per version, forever.
    function anchor(
        string calldata documentId,
        uint32 version,
        bytes32 hash,
        uint8 eventType
    ) external onlyWriter {
        bytes32 key = keccak256(abi.encodePacked(documentId, version));
        require(!anchors[key].exists, "already anchored");
        anchors[key] = Anchor(hash, version, eventType, uint64(block.timestamp), true);
        emit AnchorCreated(documentId, version, hash, eventType, uint64(block.timestamp));
    }

    /// @notice Read back a previously anchored record. `exists` is false
    /// (and every other field zero) if this (documentId, version) was
    /// never anchored.
    function getAnchor(string calldata documentId, uint32 version)
        external
        view
        returns (bytes32 hash, uint8 eventType, uint64 ts, bool exists)
    {
        Anchor storage a = anchors[keccak256(abi.encodePacked(documentId, version))];
        return (a.hash, a.eventType, a.ts, a.exists);
    }
}
