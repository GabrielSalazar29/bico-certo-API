// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

interface IBicoCertoJobManager {
    enum JobStatus {
        None,
        Created,
        Accepted,
        InProgress,
        Completed,
        Approved,
        Disputed,
        Cancelled,
        Refunded
    }

    struct Job {
        bytes32 id;
        address client;
        address provider;
        uint256 amount;
        uint256 platformFee;
        uint256 createdAt;
        uint256 acceptedAt;
        uint256 completedAt;
        uint256 deadline;
        JobStatus status;
        string serviceType;
        string ipfsHash;
        uint8 clientRating;
        uint8 providerRating;
    }

    // ========== EVENTOS ==========
    event JobCreated(
        bytes32 indexed jobId,
        address indexed client,
        address indexed provider,
        uint256 amount,
        uint256 deadline
    );
    event JobAccepted(bytes32 indexed jobId, address indexed provider, uint256 timestamp);
    event JobCompleted(bytes32 indexed jobId, address indexed provider, uint256 timestamp);
    event JobApproved(bytes32 indexed jobId, address indexed client, uint256 amount, uint256 platformFee);
    event JobCancelled(bytes32 indexed jobId, address indexed client);
    event JobDisputed(bytes32 indexed jobId, address indexed disputer);
    event RatingGiven(bytes32 indexed jobId, address indexed rater, uint8 rating);

    // ========== FUNÇÕES DIRETAS (chamadas por usuários) ==========
    function createJob(
        address _provider,
        uint256 _deadline,
        string memory _serviceType,
        string memory _ipfsHash
    ) external payable returns (bytes32);

    function acceptJob(bytes32 _jobId) external;
    function completeJob(bytes32 _jobId) external;
    function approveJob(bytes32 _jobId, uint8 _rating) external;
    function cancelJob(bytes32 _jobId) external;
    function autoApprove(bytes32 _jobId) external;

    // ========== FUNÇÕES DELEGADAS (chamadas pelo V2) ==========
    function createJobFor(
        address _client,
        address _provider,
        uint256 _deadline,
        string memory _serviceType,
        string memory _ipfsHash
    ) external payable returns (bytes32);

    function acceptJobFor(bytes32 _jobId, address _provider) external;
    function completeJobFor(bytes32 _jobId, address _provider) external;
    function approveJobFor(bytes32 _jobId, address _client, uint8 _rating) external;
    function cancelJobFor(bytes32 _jobId, address _client) external;

    // ========== FUNÇÕES DE ATUALIZAÇÃO (para contratos confiáveis) ==========
    function updateJobStatus(bytes32 _jobId, JobStatus _newStatus) external;
    function updateJobClientRating(bytes32 _jobId, uint8 _rating) external;
    function updateJobProviderRating(bytes32 _jobId, uint8 _rating) external;

    // ========== FUNÇÕES DE CONSULTA ==========
    function getJob(bytes32 _jobId) external view returns (Job memory);
    function getJobClient(bytes32 _jobId) external view returns (address);
    function getJobProvider(bytes32 _jobId) external view returns (address);
    function getJobAmount(bytes32 _jobId) external view returns (uint256);
    function getJobPlatformFee(bytes32 _jobId) external view returns (uint256);
    function getJobStatus(bytes32 _jobId) external view returns (JobStatus);
    function getJobCompletedAt(bytes32 _jobId) external view returns (uint256);
    function getUserJobs(address _user) external view returns (bytes32[] memory);

    // ========== VARIÁVEIS PÚBLICAS ==========
    // function registry() external view returns (address);
    // function minJobValue() external view returns (uint256);
    // function autoApprovalTimeout() external view returns (uint256);
    // function totalJobs() external view returns (uint256);
    // function totalVolume() external view returns (uint256);
}