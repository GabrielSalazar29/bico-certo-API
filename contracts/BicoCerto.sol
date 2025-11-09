// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "./BicoCertoRegistry.sol";
import "contracts/interfaces/IBicoCertoJobManager.sol";
import "contracts/interfaces/IBicoCertoPaymentGateway.sol";
import "contracts/interfaces/IBicoCertoReputation.sol";
import "contracts/interfaces/IBicoCertoDisputeResolver.sol";
import "contracts/interfaces/IBicoCertoAdmin.sol";

/**
 * @title BicoCerto - Sistema de Pagamentos com Escrow Automático (Modularizado)
 * @notice Gerencia trabalhos e pagamentos entre clientes e prestadores
 * @dev Compatível com futuro DREX e sistema de reputação
 */
contract BicoCerto {
    BicoCertoRegistry public registry;

    constructor(address _registryAddress) {
        registry = BicoCertoRegistry(_registryAddress);
    }

    // ====
    // FUNÇÕES PRINCIPAIS - CICLO DO TRABALHO
    // ====

    function createJob(
        address _provider,
        uint256 _deadline,
        string memory _serviceType,
        string memory _ipfsHash
    ) external payable returns (bytes32) {
        return IBicoCertoJobManager(registry.getJobManager()).createJobFor{
            value: msg.value
        }(
            msg.sender,
            _provider,
            _deadline,
            _serviceType,
            _ipfsHash
        );
    }

    function createOpenJob(
        uint256 _maxBudget,
        uint256 _deadline,
        string memory _serviceType,
        string memory _ipfsHash
    ) external payable returns (bytes32) {
        return IBicoCertoJobManager(registry.getJobManager()).createOpenJob{
            value: msg.value
        }(
            msg.sender,
            _maxBudget,
            _deadline,
            _serviceType,
            _ipfsHash
        );
    }

    function submitProposal(
        bytes32 _jobId,
        uint256 _amount,
        uint256 _estimatedTime,
        string memory _ipfsHash
    ) external returns (bytes32) {
        return IBicoCertoJobManager(registry.getJobManager()).submitProposal(
            msg.sender,
            _jobId,
            _amount,
            _estimatedTime,
            _ipfsHash
        );
    }

    function acceptProposal(bytes32 _proposalId) external payable {
        return IBicoCertoJobManager(registry.getJobManager()).acceptProposal{
            value: msg.value
        }(
            _proposalId,
            msg.sender
        );
    }

    function rejectProposal(bytes32 _proposalId) external {
        return IBicoCertoJobManager(registry.getJobManager()).rejectProposal(
            _proposalId,
            msg.sender
        );
    }

    function withdrawProposal(bytes32 _proposalId) external {
        return IBicoCertoJobManager(registry.getJobManager()).withdrawProposal(
            _proposalId,
            msg.sender
        );
    }

    function acceptJob(bytes32 _jobId) external {
        IBicoCertoJobManager(registry.getJobManager()).acceptJobFor(
            _jobId,
            msg.sender  // Prestador real
        );
    }

    function completeJob(bytes32 _jobId) external {
        IBicoCertoJobManager(registry.getJobManager()).completeJobFor(
            _jobId,
            msg.sender  // Prestador real
        );
    }

    function approveJob(bytes32 _jobId, uint8 _rating) external {
        IBicoCertoJobManager(registry.getJobManager()).approveJobFor(
            _jobId,
            msg.sender,  // Cliente real
            _rating
        );
    }

    function cancelJob(bytes32 _jobId) external {
        IBicoCertoJobManager(registry.getJobManager()).cancelJobFor(
            _jobId,
            msg.sender  // Cliente real
        );
    }

    // ====
    // SISTEMA DE DISPUTAS
    // ====

    function openDispute(bytes32 _jobId, string memory _reason) external {
        IBicoCertoDisputeResolver(registry.getDisputeResolver()).openDispute(
            _jobId,
            _reason
        );
    }

    function resolveDispute(
        bytes32 _jobId,
        bool _favorClient,
        string memory _resolution
    ) external {
        IBicoCertoDisputeResolver(registry.getDisputeResolver()).resolveDispute(
            _jobId,
            _favorClient,
            _resolution
        );
    }

    // ====
    // SISTEMA DE REPUTAÇÃO
    // ====

    function rateClient(bytes32 _jobId, uint8 _rating) external {
        IBicoCertoReputation(registry.getReputation()).rateClient(_jobId, _rating);
    }

    // ====
    // FUNÇÕES ADMINISTRATIVAS
    // ====

    function addArbitrator(address _arbitrator) external {
        IBicoCertoDisputeResolver(registry.getAdmin()).addArbitrator(_arbitrator);
    }

    function removeArbitrator(address _arbitrator) external {
        IBicoCertoDisputeResolver(registry.getAdmin()).removeArbitrator(_arbitrator);
    }

    function updatePlatformFee(uint256 _newFee) external {
        IBicoCertoAdmin(registry.getAdmin()).updatePlatformFee(_newFee);
    }

    function togglePause() external {
        IBicoCertoAdmin(registry.getAdmin()).togglePause();
    }

    // ====
    // FUNÇÕES DE CONSULTA
    // ====

    function getUserJobs(address _user) external view returns (bytes32[] memory) {
        return IBicoCertoJobManager(registry.getJobManager()).getUserJobs(_user);
    }

    function getJob(bytes32 _jobId) external view returns (IBicoCertoJobManager.Job memory) {
        return IBicoCertoJobManager(registry.getJobManager()).getJob(_jobId);
    }

    function getProposal(bytes32 _proposalId) external view returns (IBicoCertoJobManager.Proposal memory) {
        return IBicoCertoJobManager(registry.getJobManager()).getProposal(_proposalId);
    }

    function getJobProposals(bytes32 _jobId) external view returns (bytes32[] memory) {
        return IBicoCertoJobManager(registry.getJobManager()).getJobProposals(_jobId);
    }

    function getProviderProposals(address _provider) external view returns (bytes32[] memory) {
        return IBicoCertoJobManager(registry.getJobManager()).getProviderProposals(_provider);
    }

    function getOpenJobs() external view returns (bytes32[] memory) {
        return IBicoCertoJobManager(registry.getJobManager()).getOpenJobs();
    }

    function getActiveProposalsForJob(bytes32 _jobId) external view returns (IBicoCertoJobManager.Proposal[] memory) {
        return IBicoCertoJobManager(registry.getJobManager()).getActiveProposalsForJob(_jobId);
    }

    // ====
    // FUNÇÕES DE REPUTAÇÃO - NOVAS FUNÇÕES SEPARADAS
    // ====

    /**
     * @notice Retorna a avaliação média do usuário como Provider (prestador)
     * @param _provider Endereço do prestador
     * @return Média com 2 casas decimais (ex: 425 = 4.25 estrelas)
     */
    function getProviderAverageRating(address _provider) external view returns (uint256) {
        return IBicoCertoReputation(registry.getReputation()).getProviderAverageRating(_provider);
    }

    /**
     * @notice Retorna a avaliação média do usuário como Cliente
     * @param _client Endereço do cliente
     * @return Média com 2 casas decimais (ex: 425 = 4.25 estrelas)
     */
    function getClientAverageRating(address _client) external view returns (uint256) {
        return IBicoCertoReputation(registry.getReputation()).getClientAverageRating(_client);
    }

    /**
     * @notice Retorna o perfil completo do usuário como Provider
     * @param _provider Endereço do prestador
     * @return averageRating Média de avaliações (ex: 425 = 4.25)
     * @return totalRatings Total de avaliações recebidas
     * @return totalJobs Total de trabalhos realizados
     * @return totalEarned Total ganho em Wei
     */
    function getProviderProfile(address _provider) external view returns (
        uint256 averageRating,
        uint256 totalRatings,
        uint256 totalJobs,
        uint256 totalEarned
    ) {
        return IBicoCertoReputation(registry.getReputation()).getProviderProfile(_provider);
    }

    /**
     * @notice Retorna o perfil completo do usuário como Cliente
     * @param _client Endereço do cliente
     * @return averageRating Média de avaliações (ex: 425 = 4.25)
     * @return totalRatings Total de avaliações recebidas
     * @return totalJobs Total de trabalhos contratados
     * @return totalSpent Total gasto em Wei
     */
    function getClientProfile(address _client) external view returns (
        uint256 averageRating,
        uint256 totalRatings,
        uint256 totalJobs,
        uint256 totalSpent
    ) {
        return IBicoCertoReputation(registry.getReputation()).getClientProfile(_client);
    }

    /**
     * @notice Mantém compatibilidade com versão anterior (retorna dados como Provider)
     * @param _user Endereço do usuário
     * @return User Estrutura de dados do usuário
     */
    function getUserProfile(address _user) external view returns (IBicoCertoReputation.User memory) {
        return IBicoCertoReputation(registry.getReputation()).getUserProfile(_user);
    }

    function calculatePlatformFee(uint256 _amount) external view returns (uint256) {
        return IBicoCertoAdmin(registry.getAdmin()).getPlatformFeePercent() * _amount / 100;
    }

    function getRegistryAddress() external view returns (address) {
        return address(registry);
    }

    // ====
    // FALLBACK
    // ====

    receive() external payable {
        // Aceitar ETH para a plataforma
    }

    fallback() external payable {
        // Aceitar ETH para a plataforma
    }
}