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

    // Eventos
    event RatingGiven(bytes32 indexed jobId, address indexed rater, uint8 rating);
    event ProviderRated(address indexed provider, uint8 rating);
    event ClientRated(address indexed client, uint8 rating);


    function updateProviderRating(address _provider, uint8 _rating) external;

    function updateClientRating(address _client, uint8 _rating) external;

    function updateReputation(address _user, uint8 _rating, bool _positive) external;

    function updateUserStats(address _user, uint256 _amount, bool _isProvider) external;

    function rateClient(address _provider, bytes32 _jobId, uint8 _rating) external;

    function getProviderAverageRating(address _provider) external view returns (uint256);

    function getClientAverageRating(address _client) external view returns (uint256);

    function getProviderProfile(address _provider) external view returns (
        uint256 averageRating,
        uint256 totalRatings,
        uint256 totalJobs,
        uint256 totalEarned,
        uint256 joinedAt
    );

    function getClientProfile(address _client) external view returns (
        uint256 averageRating,
        uint256 totalRatings,
        uint256 totalJobs,
        uint256 totalSpent,
        uint256 joinedAt
    );
}