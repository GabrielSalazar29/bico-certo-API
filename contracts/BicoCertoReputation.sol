// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "contracts/interfaces/IBicoCertoReputation.sol";
import "contracts/interfaces/IBicoCertoJobManager.sol";
import "contracts/interfaces/IBicoCertoRegistry.sol";
import "contracts/interfaces/IBicoCertoAdmin.sol";

contract BicoCertoReputation is IBicoCertoReputation {
    IBicoCertoRegistry public registry;

    mapping(address => User) public users;

    constructor(address _registryAddress) {
    registry = IBicoCertoRegistry(_registryAddress);
    }

    modifier notPaused() {
    require(!IBicoCertoAdmin(registry.getAdmin()).isPaused(), "Contrato pausado");
    _;
    }

    function _updateReputation(
    address _user,
    uint8 _rating,
    bool _positive
    ) private {
    User storage user = users[_user];

    uint256 currentScore = user.reputationScore;
    uint256 jobWeight = 100; // Peso base por trabalho

    if (_positive) {
    uint256 increase = (_rating * jobWeight) / 5;
    user.reputationScore = currentScore + increase;
    if (user.reputationScore > 1000) {
    user.reputationScore = 1000; // Cap máximo
    }
    } else {
    uint256 decrease = ((5 - _rating) * jobWeight) / 5;
    if (currentScore > decrease) {
    user.reputationScore = currentScore - decrease;
    } else {
    user.reputationScore = 0;
    }
    }
    }

    function updateReputation(address _user, uint8 _rating, bool _positive) external notPaused {
    // Only callable by trusted contracts (e.g., JobManager, DisputeResolver)
    // Add access control if needed
    _updateReputation(_user, _rating, _positive);
    }

    function rateClient(bytes32 _jobId, uint8 _rating)
    external
    notPaused
    {
    IBicoCertoJobManager jobManager = IBicoCertoJobManager(registry.getJobManager());
    IBicoCertoJobManager.Job memory job = jobManager.getJob(_jobId);

    require(job.provider == msg.sender, "Apenas prestador");
    require(job.status == IBicoCertoJobManager.JobStatus.Approved, "Trabalho deve estar aprovado");
    require(job.providerRating == 0, "Ja avaliado");
    require(_rating <= 5, "Avaliacao invalida");

    jobManager.updateJobProviderRating(_jobId, _rating);
    _updateReputation(job.client, _rating, true);

    emit RatingGiven(_jobId, msg.sender, _rating);
    }

    function getUserProfile(address _user) external view returns (User memory) {
    return users[_user];
    }
}