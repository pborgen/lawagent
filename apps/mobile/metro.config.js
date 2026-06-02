// Default Expo Metro config. Extending it explicitly silences expo-doctor's
// custom-config warning in this nested monorepo project.
const { getDefaultConfig } = require("expo/metro-config");

const config = getDefaultConfig(__dirname);

module.exports = config;
