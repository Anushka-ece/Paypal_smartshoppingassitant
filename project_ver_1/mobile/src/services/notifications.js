/**
 * Push Notification Service (FCM & APNs Integration)
 */
export const registerForPushNotificationsAsync = async () => {
  // Mock registration token for Expo/FCM
  return 'fcm-mock-token-family-mobile-12345';
};

export const handleIncomingNotification = (notification, onAlertTriggered) => {
  if (notification?.data?.is_flagged && onAlertTriggered) {
    onAlertTriggered(notification.data);
  }
};
