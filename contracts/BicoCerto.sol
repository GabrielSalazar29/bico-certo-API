// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

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
            msg.sender,  // Cliente real
            _provider,
            _deadline,
            _serviceType,
            _ipfsHash
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
    // FUNÇÕES DE PAGAMENTO
    // ====

    function withdraw() external {
    IBicoCertoPaymentGateway(registry.getPaymentGateway()).withdraw(msg.sender);
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