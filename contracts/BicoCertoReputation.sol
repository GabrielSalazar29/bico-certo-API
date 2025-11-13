// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "contracts/interfaces/IBicoCertoReputation.sol";
import "contracts/interfaces/IBicoCertoJobManager.sol";
import "contracts/interfaces/IBicoCertoRegistry.sol";
import "contracts/interfaces/IBicoCertoAdmin.sol";

contract BicoCertoReputation is IBicoCertoReputation {
    IBicoCertoRegistry public registry;

    // Estrutura para armazenar avaliações separadas
    struct UserReputation {
        // Dados como Cliente
        uint256 totalRatingsAsClient;
        uint256 sumRatingsAsClient;
        uint256 totalJobsAsClient;
        uint256 totalSpent;

        // Dados como Provider
        uint256 totalRatingsAsProvider;
        uint256 sumRatingsAsProvider;
        uint256 totalJobsAsProvider;
        uint256 totalEarned;

        // Dados gerais
        uint256 joinedAt;
    }

    mapping(address => UserReputation) public userReputations;

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
        UserReputation storage userRep = userReputations[_user];
        if (userRep.joinedAt == 0) {
            userRep.joinedAt = block.timestamp;
        }
    }

    // ═══════════════════════════════════════════════════════
    // Funções Internas
    // ═══════════════════════════════════════════════════════

    // Função interna para atualizar avaliação do Provider
    function _updateProviderRating(
        address _provider,
        uint8 _rating
    ) internal {
        require(_rating > 0 && _rating <= 5, "Avaliacao deve estar entre 1 e 5");

        _initializeUserIfNeeded(_provider);
        UserReputation storage userRep = userReputations[_provider];

        userRep.sumRatingsAsProvider += _rating;
        userRep.totalRatingsAsProvider++;
        userRep.totalJobsAsProvider++;

        emit ProviderRated(_provider, _rating);
    }

    // Função interna para atualizar avaliação do Cliente
    function _updateClientRating(
        address _client,
        uint8 _rating
    ) internal {
        require(_rating > 0 && _rating <= 5, "Avaliacao deve estar entre 1 e 5");

        _initializeUserIfNeeded(_client);
        UserReputation storage userRep = userReputations[_client];

        userRep.sumRatingsAsClient += _rating;
        userRep.totalRatingsAsClient++;
        userRep.totalJobsAsClient++;

        emit ClientRated(_client, _rating);
    }

    // ═══════════════════════════════════════════════════════
    // Funções Públicas de Atualização
    // ═══════════════════════════════════════════════════════

    // Atualiza avaliação do Provider (prestador de serviço)
    function updateProviderRating(
        address _provider,
        uint8 _rating
    ) external notPaused onlyTrustedContracts {
        _updateProviderRating(_provider, _rating);
    }

    // Atualiza avaliação do Cliente
    function updateClientRating(
        address _client,
        uint8 _rating
    ) external notPaused onlyTrustedContracts {
        _updateClientRating(_client, _rating);
    }

    // Mantém compatibilidade com interface antiga
    function updateReputation(
        address _user,
        uint8 _rating,
        bool _positive
    ) external notPaused onlyTrustedContracts {
        require(_rating > 0 && _rating <= 5, "Avaliacao deve estar entre 1 e 5");

        _initializeUserIfNeeded(_user);
        UserReputation storage userRep = userReputations[_user];

        // Assume que é Provider por padrão para manter compatibilidade
        userRep.sumRatingsAsProvider += _rating;
        userRep.totalRatingsAsProvider++;
        userRep.totalJobsAsProvider++;
    }

    function updateUserStats(
        address _user,
        uint256 _amount,
        bool _isProvider
    ) external notPaused onlyTrustedContracts {
        _initializeUserIfNeeded(_user);
        UserReputation storage userRep = userReputations[_user];

        if (_isProvider) {
            userRep.totalEarned += _amount;
        } else {
            userRep.totalSpent += _amount;
        }
    }

    function rateClient(address _provider, bytes32 _jobId, uint8 _rating)
        external
        notPaused
    {
        IBicoCertoJobManager jobManager = IBicoCertoJobManager(registry.getJobManager());
        IBicoCertoJobManager.Job memory job = jobManager.getJob(_jobId);

        require(job.provider == _provider, "Apenas prestador");
        require(job.status == IBicoCertoJobManager.JobStatus.Approved, "Trabalho deve estar aprovado");
        require(job.providerRating == 0, "Ja avaliado");
        require(_rating > 0 && _rating <= 5, "Avaliacao deve estar entre 1 e 5");

        jobManager.updateJobProviderRating(_jobId, _rating);

        // Chama função interna ao invés de externa
        _updateClientRating(job.client, _rating);

        emit RatingGiven(_jobId, msg.sender, _rating);
    }

    // ═══════════════════════════════════════════════════════
    // Funções de Consulta
    // ═══════════════════════════════════════════════════════

    // Calcula média como Provider (com 2 casas decimais: 425 = 4.25)
    function getProviderAverageRating(address _provider) external view returns (uint256) {
        UserReputation storage userRep = userReputations[_provider];

        if (userRep.totalRatingsAsProvider == 0) {
            return 0;
        }

        // Retorna média multiplicada por 100 para ter 2 casas decimais
        return (userRep.sumRatingsAsProvider * 100) / userRep.totalRatingsAsProvider;
    }

    // Calcula média como Cliente (com 2 casas decimais: 425 = 4.25)
    function getClientAverageRating(address _client) external view returns (uint256) {
        UserReputation storage userRep = userReputations[_client];

        if (userRep.totalRatingsAsClient == 0) {
            return 0;
        }

        // Retorna média multiplicada por 100 para ter 2 casas decimais
        return (userRep.sumRatingsAsClient * 100) / userRep.totalRatingsAsClient;
    }

    // Retorna dados do usuário como Provider
    function getProviderProfile(address _provider) external view returns (
        uint256 averageRating,
        uint256 totalRatings,
        uint256 totalJobs,
        uint256 totalEarned
    ) {
        UserReputation storage userRep = userReputations[_provider];

        if (userRep.totalRatingsAsProvider > 0) {
            averageRating = (userRep.sumRatingsAsProvider * 100) / userRep.totalRatingsAsProvider;
        } else {
            averageRating = 0;
        }

        return (
            averageRating,
            userRep.totalRatingsAsProvider,
            userRep.totalJobsAsProvider,
            userRep.totalEarned
        );
    }

    // Retorna dados do usuário como Cliente
    function getClientProfile(address _client) external view returns (
        uint256 averageRating,
        uint256 totalRatings,
        uint256 totalJobs,
        uint256 totalSpent
    ) {
        UserReputation storage userRep = userReputations[_client];

        if (userRep.totalRatingsAsClient > 0) {
            averageRating = (userRep.sumRatingsAsClient * 100) / userRep.totalRatingsAsClient;
        } else {
            averageRating = 0;
        }

        return (
            averageRating,
            userRep.totalRatingsAsClient,
            userRep.totalJobsAsClient,
            userRep.totalSpent
        );
    }

    // Mantém compatibilidade com getUserProfile (retorna dados como Provider)
    function getUserProfile(address _user) external view returns (User memory) {
        UserReputation storage userRep = userReputations[_user];

        User memory user;
        user.joinedAt = userRep.joinedAt;
        user.totalJobs = userRep.totalJobsAsProvider;
        user.totalEarned = userRep.totalEarned;
        user.totalSpent = userRep.totalSpent;
        user.successfulJobs = userRep.totalJobsAsProvider;

        // Calcula reputationScore baseado na média como Provider (convertido para escala 0-1000)
        if (userRep.totalRatingsAsProvider > 0) {
            uint256 average = (userRep.sumRatingsAsProvider * 100) / userRep.totalRatingsAsProvider;
            user.reputationScore = (average * 1000) / 500; // Converte média (0-500) para escala 0-1000
        } else {
            user.reputationScore = 500; // Score inicial neutro
        }

        return user;
    }
}