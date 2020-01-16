# Challenge

`Bank` is one of my two smart contract challenges for [Balsn CTF 2019](https://github.com/balsn/balsn-ctf-2019). You may find the source files [here](https://github.com/x9453/balsn-ctf-2019).

* Type: Smart contract
* Solves: 1/720

# Description

> Again, as those ctfs did in the past, we also implemented our 100% secure bank system, but on blockchain this time.

# Solution

## TL;DR

In this challenge, our goal is to emit the `SendFlag` event. The uninitialized storage pointer `info` at line 32 allows us to overwrite the length of `safeboxes` to a large value, making `safeboxes` overlap with `failedLogs`. Thus, we can control the `callback` variable by `triedPass` in a `FailedAttempt`, and hijack the program flow to jump directly to the instruction where the `SendFlag` event is emitted.

## Detailed Write-up

We are provided with the game contract source:

```javascript=
pragma solidity ^0.4.24;

contract Bank {
    event SendEther(address addr);
    event SendFlag(address addr);
    
    address public owner;
    uint randomNumber = 0;
    
    constructor() public {
        owner = msg.sender;
    }
    
    struct SafeBox {
        bool done;
        function(uint, bytes12) internal callback;
        bytes12 hash;
        uint value;
    }
    SafeBox[] safeboxes;
    
    struct FailedAttempt {
        uint idx;
        uint time;
        bytes12 triedPass;
        address origin;
    }
    mapping(address => FailedAttempt[]) failedLogs;
    
    modifier onlyPass(uint idx, bytes12 pass) {
        if (bytes12(sha3(pass)) != safeboxes[idx].hash) {
            FailedAttempt info;
            info.idx = idx;
            info.time = now;
            info.triedPass = pass;
            info.origin = tx.origin;
            failedLogs[msg.sender].push(info);
        }
        else {
            _;
        }
    }
    
    function deposit(bytes12 hash) payable public returns(uint) {
        SafeBox box;
        box.done = false;
        box.hash = hash;
        box.value = msg.value;
        if (msg.sender == owner) {
            box.callback = sendFlag;
        }
        else {
            require(msg.value >= 1 ether);
            box.value -= 0.01 ether;
            box.callback = sendEther;
        }
        safeboxes.push(box);
        return safeboxes.length-1;
    }
    
    function withdraw(uint idx, bytes12 pass) public payable {
        SafeBox box = safeboxes[idx];
        require(!box.done);
        box.callback(idx, pass);
        box.done = true;
    }
    
    function sendEther(uint idx, bytes12 pass) internal onlyPass(idx, pass) {
        msg.sender.transfer(safeboxes[idx].value);
        emit SendEther(msg.sender);
    }
    
    function sendFlag(uint idx, bytes12 pass) internal onlyPass(idx, pass) {
        require(msg.value >= 100000000 ether);
        emit SendFlag(msg.sender);
        selfdestruct(owner);
    }

}
```

Following the game contract's logic, we may notice that `SendFlag` can be emitted only from the callback function `sendFlag()`, which happens if the safebox is deposited by the `owner`, the contract creator. However, the owner will not interact with the game contract after it was deployed, so we must exploit some vulnerabilities in the game contract to reach our goal.

### Finding the Bug

After compiling the game contract in [Remix](https://remix.ethereum.org/) (or other IDEs), several warnings popped out:

> browser/Bank.sol\:32\:13\: Warning: Uninitialized storage pointer. Did you mean '\<type\> memory info'?
> FailedAttempt info;
> \^----------------^

> browser/Bank.sol\:45\:9\: Warning: Uninitialized storage pointer. Did you mean '\<type\> memory box'?
> SafeBox box;
> \^---------^

That is, `info` at line 32 and `box` at line 45 are **uninitialized storage pointers**. In Solidity < v0.5.0, the default data location for variables of structs and arrays is `storage` ([Ref](https://solidity.readthedocs.io/en/v0.4.24/types.html#data-location)). If these variables are not declared with an initial value, they point to slot 0 in the storage by default, causing that data in slot 0 (or the next few slots) is overwritten when writing to these variables (or to the members of them).

### Storage Layout of State Variables

Before explaining how we can exploit the uninitialized pointers, we should know about the storage layout of the state variables first. If you are not familiar with the storage layout, [here](https://solidity.readthedocs.io/en/v0.4.24/miscellaneous.html#layout-of-state-variables-in-storage) is a detailed specification.

Consider the following example:

```javascript=
contract C {
    address a;
    uint r;
    uint[] b;
    mapping(uint => uint) m;
    
    constructor() public {
        a = msg.sender;
        r = 777;
        b.push(333);
        b.push(444);
        m[999] = 888;
    }
}
```

Variables `a` and `r` are stored at slot 0 and 1 respectively. Slot 2 stores the length of `b`, which is 2 in this case. Slot 3 is occupied by `m` but it is unused.

The elements of `b` are located at slot `keccak256(2)`. That is, slot `keccak256(2)+0` stores `333`, and slot `keccak256(2)+1` stores `444`. As for the mapping `m`, the value `m[k]` are stored at slot `keccak256(k||3)`, and thus `888` is stored at slot `keccak256(9||3)`.

You may include the following functions in the previous contract to calculate the slot address of variables and directly read the value of a storage slot.

```javascript=
function read_slot(uint k) public view returns (bytes32 res) {
    assembly { res := sload(k) }
}

function cal_addr(uint k, uint p) public pure returns(bytes32 res) {
    res = keccak256(abi.encodePacked(k, p));
}

function cal_addr(uint p) public pure returns(bytes32 res) {
    res = keccak256(abi.encodePacked(p));
}
```

### Exploiting the Uninitialized Storage Pointers

Back to the game contract. When the contract is created, the variables stored at slot 0 to 3 are as follow:

```
-----------------------------------------------------
|     unused (12)     |          owner (20)         | <- slot 0
-----------------------------------------------------
|                 randomNumber (32)                 | <- slot 1
-----------------------------------------------------
|               safeboxes.length (32)               | <- slot 2
-----------------------------------------------------
|       occupied by failedLogs but unused (32)      | <- slot 3
-----------------------------------------------------
```

According to the structure of `FailedAttempt`, its layout in the storage is:

```
-----------------------------------------------------
|                      idx (32)                     |
-----------------------------------------------------
|                     time (32)                     |
-----------------------------------------------------
|          origin (20)         |   triedPass (12)   |
-----------------------------------------------------
```

At line 33~36, since `info` is uninitialized and points to slot 0, modifying the members of `info` leads to overwriting the values at slot 0 to 2.

Similarly, the layout `SafeBox` is,

```
-----------------------------------------------------
| unused (11) | hash (12) | callback (8) | done (1) |
-----------------------------------------------------
|                     value (32)                    |
-----------------------------------------------------
```

and, in the function `deposit()`, slot 0 and 1 is overwritten by the members of `box`.

Notice that modifying slots 0 and 1, where the value of `owner` and `randomNumber` is stored respectively, is useless. Since even if we overwrite `owner` to our address, we should pass the check at line 74. However, if `tx.origin` is large enough, modifying the length of `safeboxes` can make it overlap with `failedLogs`. This happens with a probability of 1/2, depending on the value of `tx.origin`.

### Controlling the Flow

Now, assume that `safeboxes` overlaps with `failedLogs`, and the `callback` of a `Safebox` element overlaps with the `triedPass` of a `FailedAttempt` element. Since `triedPass` is completely controlled by us, we can overwrite `callback` and further control the program flow (at line 64) by calling `withdraw()` with the corresponding index of the overlapped safebox element.

Calling internal functions in a contract is identical to executing a `JUMP` operation. Notice that EVM only allows us to jump to a `JUMPDEST` instruction. By inspecting the assembly code of the game contract, we can notice that jumping to the instruction `0x70f` is exactly what we want. After the jump, the program continues to execute at line 75, emits the `SendFlag` event, and stops after executing the selfdestruct instruction.

So, this is our full exploit:
1. Calculate `target = keccak256(keccak256(msg.sender||3)) + 2`.
2. Calculate `base = keccak256(2)`.
3. Calculate `idx = (target - base) // 2`.
4. If `(target - base) % 2 == 1`, then `idx += 2`, and do step 7 twice. This happens when the `triedPass` of the first element of `failedLogs` does not overlap with the `callback` variable, so we choose the second element instead.
5. If `(msg.sender << (12*8)) < idx`, then choose another player account, and restart from step 1. This happens when the overwritten length of `safeboxes` is not large enough to overlap with `failedLogs`.
6. Call `deposit(0x000000000000000000000000)` with 1 ether.
7. Call `withdraw(0, 0x111111111111110000070f00)`.
8. Call `withdraw(idx, 0x000000000000000000000000)`, and the `SendFlag` event will be emitted.

# Misc

To fix the bugs in the game contract, the data location of `info` and `box` should be explicitly declared as `memory`. Starting from Solidity v5.0.0, explicit data location for all variables of the struct, array or mapping types is mandatory ([Ref](https://solidity.readthedocs.io/en/v0.5.0/050-breaking-changes.html#explicitness-requirements)).

Congrats to @Sissel for being the only person who solved my two challenges during the CTF! I hope all of you enjoy this challenge and Balsn CTF.
