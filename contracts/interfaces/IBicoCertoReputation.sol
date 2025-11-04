// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

interface IBicoCertoReputation {
    struct User {
        uint256 totalJobs;
        uint256 successfulJobs;
        uint256 totalEarned;
        uint256 totalSpent;
        uint256 reputationScore;
        uint256 joinedAt;
    }

    event RatingGiven(bytes32 indexed jobId, address indexed rater, uint8 rating);

    function updateReputation(address _user, uint8 _rating, bool _positive) external;
    function updateUserStats(address _user, uint256 _amount, bool _isProvider) external;
    function rateClient(bytes32 _jobId, uint8 _rating) external;
    function getUserProfile(address _user) external view returns (User memory);
}