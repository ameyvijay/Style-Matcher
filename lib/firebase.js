import { initializeApp, getApps } from "firebase/app";
import { getAuth, GoogleAuthProvider, signInWithRedirect, signOut } from "firebase/auth";
import { getFirestore } from "firebase/firestore";
import { getStorage } from "firebase/storage";

const firebaseConfig = {
  apiKey: "AIzaSyCBAIMVBmnnCA_nAV1KmTrrkmaB65XSOAA",
  authDomain: "style-matcher-9480d.firebaseapp.com",
  projectId: "style-matcher-9480d",
  storageBucket: "style-matcher-9480d.firebasestorage.app",
  messagingSenderId: "405095915331",
  appId: "1:405095915331:web:72b14637a116eb3ac259f6",
  measurementId: "G-13N8L2QE38"
};

// Initialize Firebase
const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApps()[0];
const auth = getAuth(app);
const db = getFirestore(app);
const storage = getStorage(app);
const googleProvider = new GoogleAuthProvider();

export { app, auth, db, storage, googleProvider, signInWithRedirect, signOut };
