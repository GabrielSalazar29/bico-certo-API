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

    modifier onlyTrustedContracts() {
        require(
            msg.sender == registry.getJobManager() ||
            msg.sender == registry.getDisputeResolver(),
            "Apenas contratos confiaveis"
        );
        _;
    }

    modifier notPaused() {
    require(!IBicoCertoAdmin(registry.getAdmin()).isPaused(), "Contrato pausado");
    _;
    }

    function _initializeUserIfNeeded(address _user) private {
        User storage user = users[_user];
        if (user.joinedAt == 0) {
            user.joinedAt = block.timestamp;
            user.reputationScore = 500; // Score inicial neutro
        }
    }

    function _updateReputation(
        address _user,
        uint8 _rating,
        bool _positive
    ) private {
        _initializeUserIfNeeded(_user);
        User storage user = users[_user];

        uint256 currentScore = user.reputationScore;
        uint256 baseWeight = 20; // Peso base reduzido para melhor granularidade

        // Sistema de peso dinâmico baseado no histórico
        uint256 experienceMultiplier = 100;
        if (user.totalJobs > 50) {
            experienceMultiplier = 80; // Menos impacto para usuários experientes
        } else if (user.totalJobs > 20) {
            experienceMultiplier = 90;
        }

        if (_positive) {
            // Cálculo mais sofisticado para reputação positiva
            uint256 baseIncrease = (_rating * baseWeight * experienceMultiplier) / 500;

            // Bônus por avaliação máxima
            if (_rating == 5) {
                baseIncrease = (baseIncrease * 110) / 100; // 10% de bônus
            }

            user.reputationScore = currentScore + baseIncrease;
            if (user.reputationScore > 1000) {
                user.reputationScore = 1000; // Cap máximo
            }

            user.successfulJobs++;
        } else {
            // Penalidade para avaliações negativas
            uint256 penalty = ((5 - _rating) * baseWeight * experienceMultiplier) / 500;

            // Penalidade extra para avaliações muito baixas
            if (_rating <= 2) {
                penalty = (penalty * 150) / 100; // 50% mais severo
            }

            if (currentScore > penalty) {
                user.reputationScore = currentScore - penalty;
            } else {
                user.reputationScore = 0;
            }
        }

        user.totalJobs++;
    }

    function updateReputation(
        address _user,
        uint8 _rating,
        bool _positive
    ) external notPaused onlyTrustedContracts {
        require(_rating > 0 && _rating <= 5, "Avaliacao deve estar entre 1 e 5");
        _updateReputation(_user, _rating, _positive);
    }

    function updateUserStats(
        address _user,
        uint256 _amount,
        bool _isProvider
    ) external notPaused onlyTrustedContracts {
        _initializeUserIfNeeded(_user);
        User storage user = users[_user];

        if (_isProvider) {
            user.totalEarned += _amount;
        } else {
            user.totalSpent += _amount;
        }
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
        require(_rating > 0 && _rating <= 5, "Avaliacao deve estar entre 1 e 5");

        jobManager.updateJobProviderRating(_jobId, _rating);
        _updateReputation(job.client, _rating, true);

        emit RatingGiven(_jobId, msg.sender, _rating);
    }

    function getUserProfile(address _user) external view returns (User memory) {
    return users[_user];
    }
}