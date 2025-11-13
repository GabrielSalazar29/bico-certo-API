// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

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

    mapping(bytes32 => Proposal) public proposals;
    mapping(bytes32 => bytes32[]) public jobProposals;  // jobId => proposalIds[]
    mapping(address => bytes32[]) public providerProposals;  // provider => proposalIds[]
    bytes32[] public openJobs;
    uint256 public totalProposals;

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

    // ========== FUNÇÕES DELEGADAS ==========

    function createJobFor(
        address _sender,
        address _provider,
        uint256 _deadline,
        string memory _serviceType,
        string memory _ipfsHash
    ) external payable onlyMainContract notPaused returns (bytes32) {
        return _createJob(_sender, _provider, _deadline, _serviceType, _ipfsHash, msg.value);
    }

    function acceptJobFor(bytes32 _jobId, address _sender)
        external
        onlyMainContract
        notPaused
        jobExists(_jobId)
    {
        _acceptJob(_jobId, _sender);
    }

    function completeJobFor(bytes32 _jobId, address _sender)
        external
        onlyMainContract
        notPaused
        jobExists(_jobId)
    {
        _completeJob(_jobId, _sender);
    }

    function approveJobFor(bytes32 _jobId, address _sender, uint8 _rating)
        external
        onlyMainContract
        notPaused
        jobExists(_jobId)
    {
        _approveJob(_jobId, _sender, _rating);
    }

    function cancelJobFor(bytes32 _jobId, address _sender)
        external
        onlyMainContract
        notPaused
        jobExists(_jobId)
    {
        _cancelJob(_jobId, _sender);
    }

    function createOpenJob(
        address _sender,
        uint256 _maxBudget,
        uint256 _deadline,
        string memory _serviceType,
        string memory _ipfsHash
    ) external payable notPaused returns (bytes32) {
        require(msg.value >= minJobValue, "Valor abaixo do minimo");
        require(msg.value >= _maxBudget, "Deposito insuficiente para o budget");
        require(_deadline > block.timestamp, "Prazo invalido");

        bytes32 jobId = keccak256(
            abi.encodePacked(_sender, "open", block.timestamp, totalJobs)
        );

        uint256 platformFeePercent = IBicoCertoAdmin(registry.getAdmin()).getPlatformFeePercent();
        uint256 platformFee = (_maxBudget * platformFeePercent) / 100;
        uint256 jobAmount = _maxBudget - platformFee;

        jobs[jobId] = Job({
            id: jobId,
            client: _sender,
            provider: address(0),  // Sem provider definido
            amount: jobAmount,
            platformFee: platformFee,
            createdAt: block.timestamp,
            acceptedAt: 0,
            completedAt: 0,
            deadline: _deadline,
            status: JobStatus.Open,
            serviceType: _serviceType,
            ipfsHash: _ipfsHash,
            clientRating: 0,
            providerRating: 0,
            openForProposals: true,
            proposalCount: 0
        });

        userJobs[_sender].push(jobId);
        openJobs.push(jobId);
        totalJobs++;
        totalVolume += msg.value;

        // Enviar fundos para PaymentGateway
        IBicoCertoPaymentGateway paymentGateway = IBicoCertoPaymentGateway(
            registry.getPaymentGateway()
        );
        (bool success, ) = address(paymentGateway).call{value: msg.value}("");
        require(success, "Falha ao transferir fundos");

        emit JobOpenForProposals(jobId, _sender, _maxBudget, _deadline);
        return jobId;
    }

    // ========== SUBMETER PROPOSTA ==========
    function submitProposal(
        address _sender,
        bytes32 _jobId,
        uint256 _amount,
        uint256 _estimatedTime,
        string memory _ipfsHash
    ) external notPaused returns (bytes32) {
        Job storage job = jobs[_jobId];

        require(job.status == JobStatus.Open, "Job nao esta aberto para propostas");
        require(job.openForProposals, "Job nao aceita propostas");
        require(job.client != _sender, "Cliente nao pode fazer proposta");
        require(_amount > 0, "Valor invalido");
        require(_amount <= job.amount + job.platformFee, "Valor acima do budget");
        require(_estimatedTime > 0, "Tempo estimado invalido");

        // Verificar se provider já tem proposta para este job
        bytes32[] memory existingProposals = jobProposals[_jobId];
        for (uint i = 0; i < existingProposals.length; i++) {
            if (proposals[existingProposals[i]].provider == _sender &&
                proposals[existingProposals[i]].status == ProposalStatus.Pending) {
                revert("Provider ja tem proposta pendente para este job");
            }
        }

        bytes32 proposalId = keccak256(
            abi.encodePacked(_jobId, _sender, block.timestamp, totalProposals)
        );

        proposals[proposalId] = Proposal({
            proposalId: proposalId,
            jobId: _jobId,
            provider: _sender,
            amount: _amount,
            estimatedTime: _estimatedTime,
            createdAt: block.timestamp,
            status: ProposalStatus.Pending,
            ipfsHash: _ipfsHash
        });

        jobProposals[_jobId].push(proposalId);
        providerProposals[_sender].push(proposalId);
        job.proposalCount++;
        totalProposals++;

        emit ProposalSubmitted(proposalId, _jobId, _sender, _amount);
        return proposalId;
    }

    // ========== ACEITAR PROPOSTA ==========
    function acceptProposal(bytes32 _proposalId, address _sender) external payable notPaused {
        Proposal storage proposal = proposals[_proposalId];
        Job storage job = jobs[proposal.jobId];

        require(proposal.status == ProposalStatus.Pending, "Proposta nao esta pendente");
        require(job.client == _sender, "Apenas cliente pode aceitar");
        require(job.status == JobStatus.Open, "Job nao esta aberto");

        // Calcular diferença se proposta for menor que budget original
        uint256 originalTotal = job.amount + job.platformFee;
        uint256 proposalTotal = proposal.amount;

        if (proposalTotal < originalTotal) {
            // Retornar diferença ao cliente
            uint256 refund = originalTotal - proposalTotal;
            IBicoCertoPaymentGateway(registry.getPaymentGateway()).refundClient(
                proposal.jobId,
                _sender,
                refund
            );
        } else if (proposalTotal > originalTotal) {
            // Cliente precisa adicionar mais fundos
            require(msg.value >= proposalTotal - originalTotal, "Fundos adicionais necessarios");

            // Enviar fundos adicionais para PaymentGateway
            IBicoCertoPaymentGateway paymentGateway = IBicoCertoPaymentGateway(
                registry.getPaymentGateway()
            );
            (bool success, ) = address(paymentGateway).call{value: msg.value}("");
            require(success, "Falha ao transferir fundos adicionais");
        }

        // Recalcular platform fee
        uint256 platformFeePercent = IBicoCertoAdmin(registry.getAdmin()).getPlatformFeePercent();
        job.platformFee = (proposalTotal * platformFeePercent) / 100;
        job.amount = proposalTotal - job.platformFee;

        // Atualizar job
        job.provider = proposal.provider;
        job.status = JobStatus.Accepted;
        job.acceptedAt = block.timestamp;
        job.openForProposals = false;

        // Atualizar proposta
        proposal.status = ProposalStatus.Accepted;

        // Adicionar job à lista do provider
        userJobs[proposal.provider].push(proposal.jobId);

        // Remover dos jobs abertos
        _removeFromOpenJobs(proposal.jobId);

        // Rejeitar automaticamente outras propostas
        _rejectOtherProposals(proposal.jobId, _proposalId);

        emit ProposalAccepted(_proposalId, proposal.jobId, proposal.provider, proposal.amount);
        emit JobAccepted(proposal.jobId, proposal.provider, block.timestamp);
    }

    // ========== REJEITAR PROPOSTA ==========
    function rejectProposal(bytes32 _proposalId, address _sender) external notPaused {
        Proposal storage proposal = proposals[_proposalId];
        Job storage job = jobs[proposal.jobId];

        require(proposal.status == ProposalStatus.Pending, "Proposta nao esta pendente");
        require(job.client == _sender, "Apenas cliente pode rejeitar");

        proposal.status = ProposalStatus.Rejected;

        emit ProposalRejected(_proposalId, proposal.jobId, proposal.provider);
    }

    // ========== RETIRAR PROPOSTA ==========
    function withdrawProposal(bytes32 _proposalId, address _sender) external notPaused {
        Proposal storage proposal = proposals[_proposalId];

        require(proposal.provider == _sender, "Apenas provider pode retirar");
        require(proposal.status == ProposalStatus.Pending, "Proposta nao esta pendente");

        proposal.status = ProposalStatus.Withdrawn;

        Job storage job = jobs[proposal.jobId];
        if (job.proposalCount > 0) {
            job.proposalCount--;
        }

        emit ProposalWithdrawn(_proposalId, proposal.jobId, _sender);
    }

    // ========== FUNÇÕES AUXILIARES ==========
    function _removeFromOpenJobs(bytes32 _jobId) private {
        for (uint i = 0; i < openJobs.length; i++) {
            if (openJobs[i] == _jobId) {
                openJobs[i] = openJobs[openJobs.length - 1];
                openJobs.pop();
                break;
            }
        }
    }

    function _rejectOtherProposals(bytes32 _jobId, bytes32 _acceptedProposalId) private {
        bytes32[] memory proposalIds = jobProposals[_jobId];
        for (uint i = 0; i < proposalIds.length; i++) {
            if (proposalIds[i] != _acceptedProposalId &&
                proposals[proposalIds[i]].status == ProposalStatus.Pending) {
                proposals[proposalIds[i]].status = ProposalStatus.Rejected;
                emit ProposalRejected(
                    proposalIds[i],
                    _jobId,
                    proposals[proposalIds[i]].provider
                );
            }
        }
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
            providerRating: 0,
            openForProposals: false,
            proposalCount: 0
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

        IBicoCertoReputation reputation = IBicoCertoReputation(registry.getReputation());
        reputation.updateReputation(job.provider, _rating, true);

        // Atualizar estatísticas de ganhos e gastos
        reputation.updateUserStats(job.provider, job.amount, true);
        reputation.updateUserStats(job.client, job.amount, false);

        emit JobApproved(_jobId, _client, job.amount, job.platformFee);
    }


    function cancelOpenJob(bytes32 _jobId, address _sender) external notPaused {
        Job storage job = jobs[_jobId];

        require(job.client == _sender, "Apenas cliente pode cancelar");
        require(job.status == JobStatus.Open, "Apenas jobs abertos podem ser cancelados");
        require(job.openForProposals, "Job nao esta mais aberto");

        job.status = JobStatus.Cancelled;
        job.openForProposals = false;

        bytes32[] memory proposalIds = jobProposals[_jobId];
        for (uint i = 0; i < proposalIds.length; i++) {
            if (proposals[proposalIds[i]].status == ProposalStatus.Pending) {
                proposals[proposalIds[i]].status = ProposalStatus.Rejected;

                emit ProposalRejected(
                    proposalIds[i],
                    _jobId,
                    proposals[proposalIds[i]].provider
                );
            }
        }

        _removeFromOpenJobs(_jobId);

        IBicoCertoPaymentGateway(registry.getPaymentGateway()).refundClient(
            _jobId,
            job.client,
            job.amount + job.platformFee
        );

        emit JobCancelled(_jobId, _sender);
    }

    function rejectCompletedJob(bytes32 _jobId, address _sender) external notPaused {
        Job storage job = jobs[_jobId];

        require(job.client == _sender, "Apenas cliente pode reprovar");
        require(job.status == JobStatus.Completed, "Job nao esta completo");

        job.status = JobStatus.InProgress;
        job.completedAt = 0;

        emit JobRejected(_jobId, _sender, block.timestamp);
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

        IBicoCertoReputation reputation = IBicoCertoReputation(registry.getReputation());
        reputation.updateReputation(job.provider, 5, true);

        // Atualizar estatísticas de ganhos e gastos
        reputation.updateUserStats(job.provider, job.amount, true);
        reputation.updateUserStats(job.client, job.amount, false);

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

    function getProposal(bytes32 _proposalId) external view returns (Proposal memory) {
        return proposals[_proposalId];
    }

    function getJobProposals(bytes32 _jobId) external view returns (bytes32[] memory) {
        return jobProposals[_jobId];
    }

    function getProviderProposals(address _provider) external view returns (bytes32[] memory) {
        return providerProposals[_provider];
    }

    function getOpenJobs() external view returns (bytes32[] memory) {
        return openJobs;
    }

    function getActiveProposalsForJob(bytes32 _jobId) external view returns (Proposal[] memory) {
        bytes32[] memory proposalIds = jobProposals[_jobId];
        uint256 activeCount = 0;

        // Contar propostas ativas
        for (uint i = 0; i < proposalIds.length; i++) {
            if (proposals[proposalIds[i]].status == ProposalStatus.Pending) {
                activeCount++;
            }
        }

        // Criar array com propostas ativas
        Proposal[] memory activeProposals = new Proposal[](activeCount);
        uint256 index = 0;

        for (uint i = 0; i < proposalIds.length; i++) {
            if (proposals[proposalIds[i]].status == ProposalStatus.Pending) {
                activeProposals[index] = proposals[proposalIds[i]];
                index++;
            }
        }

        return activeProposals;
    }
}