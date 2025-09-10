# compile_contracts.py
import solcx
import os
import json

def compile_contracts():
    """
    Compila todos os contratos Solidity do projeto usando a versão especificada do solc.
    """
    # Defina a versão do solc a ser utilizada, compatível com as declarações de pragma
    solc_version = '0.8.20'
    
    # Instala e configura a versão do solc
    print(f"Instalando e configurando a versão do solc para {solc_version}...")
    solcx.install_solc(solc_version)
    solcx.set_solc_version(solc_version)

    contracts_to_compile = [
        "BicoCertoAdmin.sol",
        "BicoCertoDisputeResolver.sol",
        "BicoCertoJobManager.sol",
        "BicoCertoPaymentGateway.sol",
        "BicoCertoRegistry.sol",
        "BicoCertoReputation.sol",
        "BicoCerto.sol"
    ]

    # Cria o diretório de build se não existir
    if not os.path.exists('build'):
        os.makedirs('build')

    # Compila cada contrato
    for contract_file in contracts_to_compile:
        contract_file_path = f"./contracts/{contract_file}"
        if not os.path.exists(contract_file_path):
            print(f"Aviso: {contract_file} não encontrado. Pulando.")
            continue
            
        print(f"Compilando {contract_file}...")
        try:
            compiled_sol = solcx.compile_files(
                [contract_file_path],
                output_values=["abi", "bin"],
                solc_version=solc_version,
                import_remappings={
                    "./": "" # Garante caminhos de importação corretos
                },
                optimize=True,          # <-- Parâmetro correto para ativar o otimizador
                optimize_runs=200,  
                via_ir=True # <-- Adicionada a compilação via-IR
            )
            
            # Salva os arquivos ABI e BIN
            for contract_name_long, contract_data in compiled_sol.items():
                contract_name = contract_name_long.split(':')[-1]
                
                # Escreve o ABI
                with open(f'build/{contract_name}_sol_{contract_name}.abi', 'w') as f:
                    json.dump(contract_data['abi'], f, indent=4)
                
                # Escreve o BIN
                with open(f'build/{contract_name}_sol_{contract_name}.bin', 'w') as f:
                    f.write(contract_data['bin'])

        except Exception as e:
            print(f"Erro ao compilar {contract_file}: {e}")

    print("\nCompilação concluída com sucesso!")

if __name__ == "__main__":
    compile_contracts()