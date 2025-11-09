// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "contracts/interfaces/IBicoCertoPaymentGateway.sol";
import "contracts/interfaces/IBicoCertoRegistry.sol";
import "contracts/interfaces/IBicoCertoAdmin.sol";

contract BicoCertoPaymentGateway is IBicoCertoPaymentGateway {
    IBicoCertoRegistry public registry;
    address public platformWallet;

    constructor(address _registryAddress, address _platformWallet) {
        registry = IBicoCertoRegistry(_registryAddress);
        platformWallet = _platformWallet;
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

    function releasePayment(
        bytes32 _jobId,
        address _provider,
        uint256 _amount,
        uint256 _platformFee
    ) external notPaused onlyTrustedContracts {
        require(_provider != address(0), "Provider invalido");
        require(_amount > 0, "Valor invalido");

        // Transferir taxa da plataforma automaticamente
        if (_platformFee > 0) {
            (bool platformSuccess, ) = platformWallet.call{value: _platformFee}("");
            require(platformSuccess, "Falha ao transferir taxa da plataforma");
        }

        // Transferir pagamento para o provider automaticamente
        (bool providerSuccess, ) = _provider.call{value: _amount}("");
        require(providerSuccess, "Falha ao transferir pagamento para provider");

        emit PaymentReleased(_jobId, _provider, _amount);
    }

    function refundClient(
        bytes32 _jobId,
        address _client,
        uint256 _amount
    ) external notPaused onlyTrustedContracts {
        require(_client != address(0), "Cliente invalido");
        require(_amount > 0, "Valor invalido");

        // Transferir reembolso automaticamente para o cliente
        (bool success, ) = _client.call{value: _amount}("");
        require(success, "Falha ao transferir reembolso");

        emit RefundIssued(_jobId, _client, _amount);
    }

    receive() external payable {
        // Accept ETH for the platform
    }

    fallback() external payable {
        // Accept ETH for the platform
    }
}