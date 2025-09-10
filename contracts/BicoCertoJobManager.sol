// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "contracts/interfaces/IBicoCertoJobManager.sol";
import "contracts/interfaces/IBicoCertoPaymentGateway.sol";
import "contracts/interfaces/IBicoCertoReputation.sol";
import "contracts/interfaces/IBicoCertoDisputeResolver.sol";
import "contracts/interfaces/IBicoCertoRegistry.sol";
import "contracts/interfaces/IBicoCertoAdmin.sol";

contract BicoCertoJobManager is IBicoCertoJobManager {
    IBicoCertoRegistry public registry;
    address public bicoCertoAddress;

    mapping(bytes32 => Job) public jobs;
    mapping(address => bytes32[]) public userJobs;
    uint256 public totalJobs;
    uint256 public totalVolume;

    uint256 public minJobValue;
    uint256 public autoApprovalTimeout;

    constructor(
        address _registryAddress, 
        address _bicoCertoAddress,
        uint256 _minJobValue, 
        uint256 _autoApprovalTimeout
    ) {
        registry = IBicoCertoRegistry(_registryAddress);
        bicoCertoAddress = _bicoCertoAddress;
        minJobValue = _minJobValue;
        autoApprovalTimeout = _autoApprovalTimeout;
    }

    modifier notPaused() {
        require(!IBicoCertoAdmin(registry.getAdmin()).isPaused(), "Contrato pausado");
        _;
    }

    modifier jobExists(bytes32 _jobId) {
        require(jobs[_jobId].status != JobStatus.None, "Trabalho nao existe");
        _;
    }

    modifier onlyMainContract() {
        require(msg.sender == bicoCertoAddress, "Apenas contrato principal");
        _;
    }

    // ========== FUNÇÕES ORIGINAIS (para chamadas diretas) ==========

    function createJob(
        address _provider,
        uint256 _deadline,
        string memory _serviceType,
        string memory _ipfsHash
    ) external payable notPaused returns (bytes32) {
        return _createJob(msg.sender, _provider, _deadline, _serviceType, _ipfsHash, msg.value);
    }

    function acceptJob(bytes32 _jobId) external notPaused jobExists(_jobId) {
        _acceptJob(_jobId, msg.sender);
    }

    function completeJob(bytes32 _jobId) external notPaused jobExists(_jobId) {
        _completeJob(_jobId, msg.sender);
    }

    function approveJob(bytes32 _jobId, uint8 _rating) external notPaused jobExists(_jobId) {
        _approveJob(_jobId, msg.sender, _rating);
    }

    function cancelJob(bytes32 _jobId) external notPaused jobExists(_jobId) {
        _cancelJob(_jobId, msg.sender);
    }

    // ========== FUNÇÕES DELEGADAS (para chamadas do V2) ==========

    function createJobFor(
        address _client,
        address _provider,
        uint256 _deadline,
        string memory _serviceType,
        string memory _ipfsHash
    ) external payable onlyMainContract notPaused returns (bytes32) {
        return _createJob(_client, _provider, _deadline, _serviceType, _ipfsHash, msg.value);
    }

    function acceptJobFor(bytes32 _jobId, address _provider) 
        external 
        onlyMainContract 
        notPaused 
        jobExists(_jobId) 
    {
        _acceptJob(_jobId, _provider);
    }

    function completeJobFor(bytes32 _jobId, address _provider) 
        external 
        onlyMainContract 
        notPaused 
        jobExists(_jobId) 
    {
        _completeJob(_jobId, _provider);
    }

    function approveJobFor(bytes32 _jobId, address _client, uint8 _rating) 
        external 
        onlyMainContract 
        notPaused 
        jobExists(_jobId) 
    {
        _approveJob(_jobId, _client, _rating);
    }

    function cancelJobFor(bytes32 _jobId, address _client) 
        external 
        onlyMainContract 
        notPaused 
        jobExists(_jobId) 
    {
        _cancelJob(_jobId, _client);
    }

    // ========== LÓGICA INTERNA ==========

    function _createJob(
        address _client,
        address _provider,
        uint256 _deadline,
        string memory _serviceType,
        string memory _ipfsHash,
        uint256 _value
    ) private returns (bytes32) {
        require(_value >= minJobValue, "Valor abaixo do minimo");
        require(_provider != address(0), "Prestador invalido");
        require(_provider != _client, "Nao pode contratar voce mesmo");
        require(_deadline > block.timestamp, "Prazo invalido");

        uint256 platformFeePercent = IBicoCertoAdmin(registry.getAdmin()).getPlatformFeePercent();
        uint256 platformFee = (_value * platformFeePercent) / 100;
        uint256 jobAmount = _value - platformFee;

        bytes32 jobId = keccak256(
            abi.encodePacked(_client, _provider, block.timestamp, totalJobs)
        );

        jobs[jobId] = Job({
            id: jobId,
            client: _client,
            provider: _provider,
            amount: jobAmount,
            platformFee: platformFee,
            createdAt: block.timestamp,
            acceptedAt: 0,
            completedAt: 0,
            deadline: _deadline,
            status: JobStatus.Created,
            serviceType: _serviceType,
            ipfsHash: _ipfsHash,
            clientRating: 0,
            providerRating: 0
        });

        userJobs[_client].push(jobId);
        userJobs[_provider].push(jobId);
        totalJobs++;
        totalVolume += _value;

        IBicoCertoPaymentGateway paymentGateway = IBicoCertoPaymentGateway(
            registry.getPaymentGateway()
        );
        
        // Enviar ETH para o PaymentGateway guardar
        (bool success, ) = address(paymentGateway).call{value: _value}("");
        require(success, "Falha ao transferir fundos para custodia");

        emit JobCreated(jobId, _client, _provider, jobAmount, _deadline);
        return jobId;
    }

    function _acceptJob(bytes32 _jobId, address _provider) private {
        Job storage job = jobs[_jobId];
        require(job.provider == _provider, "Apenas prestador");
        require(job.status == JobStatus.Created, "Trabalho nao esta disponivel");
        require(block.timestamp < job.deadline, "Prazo expirado");

        job.status = JobStatus.Accepted;
        job.acceptedAt = block.timestamp;

        emit JobAccepted(_jobId, _provider, block.timestamp);
    }

    function _completeJob(bytes32 _jobId, address _provider) private {
        Job storage job = jobs[_jobId];
        require(job.provider == _provider, "Apenas prestador");
        require(
            job.status == JobStatus.Accepted || 
            job.status == JobStatus.InProgress,
            "Trabalho nao pode ser completado"
        );

        job.status = JobStatus.Completed;
        job.completedAt = block.timestamp;

        emit JobCompleted(_jobId, _provider, block.timestamp);
    }

    function _approveJob(bytes32 _jobId, address _client, uint8 _rating) private {
        Job storage job = jobs[_jobId];
        require(job.client == _client, "Apenas cliente");
        require(job.status == JobStatus.Completed, "Trabalho nao esta completo");
        require(_rating <= 5, "Avaliacao invalida");

        job.status = JobStatus.Approved;
        job.clientRating = _rating;

        IBicoCertoPaymentGateway(registry.getPaymentGateway()).releasePayment(
            _jobId,
            job.provider,
            job.amount,
            job.platformFee
        );

        IBicoCertoReputation(registry.getReputation()).updateReputation(
            job.provider, 
            _rating, 
            true
        );

        emit JobApproved(_jobId, _client, job.amount, job.platformFee);
        // emit IBicoCertoReputation.RatingGiven(_jobId, _client, _rating);
    }

    function _cancelJob(bytes32 _jobId, address _client) private {
        Job storage job = jobs[_jobId];
        require(job.client == _client, "Apenas cliente");
        require(job.status == JobStatus.Created, "Trabalho nao pode ser cancelado");

        job.status = JobStatus.Cancelled;

        IBicoCertoPaymentGateway(registry.getPaymentGateway()).refundClient(
            _jobId,
            job.client,
            job.amount + job.platformFee
        );

        emit JobCancelled(_jobId, _client);
    }

    // ========== AUTO-APPROVE (não precisa de delegação) ==========

    function autoApprove(bytes32 _jobId) external notPaused jobExists(_jobId) {
        Job storage job = jobs[_jobId];
        require(job.status == JobStatus.Completed, "Trabalho nao esta completo");
        require(
            block.timestamp >= job.completedAt + autoApprovalTimeout,
            "Timeout ainda nao alcancado"
        );

        job.status = JobStatus.Approved;
        job.clientRating = 5;

        IBicoCertoPaymentGateway(registry.getPaymentGateway()).releasePayment(
            _jobId,
            job.provider,
            job.amount,
            job.platformFee
        );

        IBicoCertoReputation(registry.getReputation()).updateReputation(
            job.provider, 
            5, 
            true
        );

        emit JobApproved(_jobId, job.client, job.amount, job.platformFee);
    }

    // ========== FUNÇÕES DE CONSULTA (não modificadas) ==========

    function getJob(bytes32 _jobId) external view returns (Job memory) {
        return jobs[_jobId];
    }

    function updateJobStatus(bytes32 _jobId, JobStatus _newStatus) external {
        // Adicionar controle de acesso se necessário
        jobs[_jobId].status = _newStatus;
    }

    function updateJobClientRating(bytes32 _jobId, uint8 _rating) external {
        jobs[_jobId].clientRating = _rating;
    }

    function updateJobProviderRating(bytes32 _jobId, uint8 _rating) external {
        jobs[_jobId].providerRating = _rating;
    }

    function getJobClient(bytes32 _jobId) external view returns (address) {
        return jobs[_jobId].client;
    }

    function getJobProvider(bytes32 _jobId) external view returns (address) {
        return jobs[_jobId].provider;
    }

    function getJobAmount(bytes32 _jobId) external view returns (uint256) {
        return jobs[_jobId].amount;
    }

    function getJobPlatformFee(bytes32 _jobId) external view returns (uint256) {
        return jobs[_jobId].platformFee;
    }

    function getJobStatus(bytes32 _jobId) external view returns (JobStatus) {
        return jobs[_jobId].status;
    }

    function getJobCompletedAt(bytes32 _jobId) external view returns (uint256) {
        return jobs[_jobId].completedAt;
    }

    function getUserJobs(address _user) external view returns (bytes32[] memory) {
        return userJobs[_user];
    }
}