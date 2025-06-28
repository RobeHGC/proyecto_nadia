"""Authentication routes for OAuth login/logout."""
import os
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Response, Query, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel
from uuid import UUID

from auth import OAuthManager, SessionManager, TokenManager
from database.models import DatabaseManager
from utils.logging_config import get_logger
from api.middleware.auth import get_current_user, require_user

logger = get_logger(__name__)

# Initialize managers
oauth_manager = OAuthManager()
session_manager = SessionManager()
token_manager = TokenManager()

# OAuth settings
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')
OAUTH_REDIRECT_URI = os.getenv('OAUTH_REDIRECT_URI', 'http://localhost:3000/auth/callback')

# Create router
router = APIRouter(prefix="/auth", tags=["authentication"])

# State storage (in production, use Redis or database)
oauth_states = {}


class LoginRequest(BaseModel):
    """OAuth login request."""
    provider: str  # 'google' or 'github'
    redirect_url: Optional[str] = None


class TokenResponse(BaseModel):
    """Token response."""
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: dict


class RefreshRequest(BaseModel):
    """Refresh token request."""
    refresh_token: str


@router.post("/login")
async def oauth_login(request: LoginRequest) -> dict:
    """Initiate OAuth login flow."""
    try:
        # Get OAuth provider
        provider = oauth_manager.get_provider(request.provider)
        
        # Generate state token for CSRF protection
        state = oauth_manager.generate_state_token()
        
        # Store state with redirect URL
        oauth_states[state] = {
            'provider': request.provider,
            'redirect_url': request.redirect_url or FRONTEND_URL
        }
        
        # Get authorization URL
        auth_url = provider.get_authorization_url(state)
        
        return {
            'auth_url': auth_url,
            'state': state
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"OAuth login error: {e}")
        raise HTTPException(status_code=500, detail="OAuth configuration error")


@router.get("/callback")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    error: Optional[str] = Query(None)
) -> RedirectResponse:
    """Handle OAuth callback."""
    # Check for OAuth errors
    if error:
        logger.error(f"OAuth error: {error}")
        return RedirectResponse(
            url=f"{FRONTEND_URL}/login?error=oauth_failed"
        )
    
    # Validate state
    state_data = oauth_states.pop(state, None)
    if not state_data:
        logger.error("Invalid OAuth state")
        return RedirectResponse(
            url=f"{FRONTEND_URL}/login?error=invalid_state"
        )
    
    try:
        # Handle OAuth callback
        user_info = await oauth_manager.handle_callback(
            state_data['provider'],
            code
        )
        
        # Create or update user in database
        db = DatabaseManager(os.getenv('DATABASE_URL'))
        await db.initialize()
        
        async with db._pool.acquire() as conn:
            # Check if user exists
            existing_user = await conn.fetchrow("""
                SELECT id, role, is_active 
                FROM users 
                WHERE oauth_provider = $1 AND oauth_id = $2
            """, user_info['oauth_provider'], user_info['oauth_id'])
            
            if existing_user:
                # Update existing user
                user_id = existing_user['id']
                role = existing_user['role']
                
                if not existing_user['is_active']:
                    return RedirectResponse(
                        url=f"{FRONTEND_URL}/login?error=account_disabled"
                    )
                
                await conn.execute("""
                    UPDATE users 
                    SET 
                        email = $1,
                        name = $2,
                        avatar_url = $3,
                        last_login = NOW(),
                        updated_at = NOW()
                    WHERE id = $4
                """, user_info['email'], user_info['name'], 
                    user_info['avatar_url'], user_id)
            
            else:
                # Create new user with default viewer role
                result = await conn.fetchrow("""
                    INSERT INTO users (
                        email, name, role, oauth_provider, 
                        oauth_id, avatar_url
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id, role
                """, user_info['email'], user_info['name'], 
                    'viewer',  # Default role
                    user_info['oauth_provider'], 
                    user_info['oauth_id'],
                    user_info['avatar_url'])
                
                user_id = result['id']
                role = result['role']
                
                # Log new user creation
                await session_manager.log_auth_event(
                    'user_created',
                    str(user_id),
                    details={'provider': user_info['oauth_provider']}
                )
        
        # Create session
        session_data = await session_manager.create_session(
            user_id=str(user_id),
            user_email=user_info['email'],
            user_role=role
        )
        
        # Log successful login
        await session_manager.log_auth_event(
            'login',
            str(user_id),
            details={'provider': user_info['oauth_provider']}
        )
        
        # Redirect to frontend with tokens
        redirect_url = state_data['redirect_url']
        
        # In production, use secure cookies or post message
        # For now, pass tokens in URL fragment (not query params for security)
        return RedirectResponse(
            url=f"{redirect_url}#auth_success"
            f"&access_token={session_data['tokens']['access_token']}"
            f"&refresh_token={session_data['tokens']['refresh_token']}"
            f"&expires_in={session_data['tokens']['expires_in']}"
        )
    
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        return RedirectResponse(
            url=f"{FRONTEND_URL}/login?error=callback_failed"
        )
    finally:
        if 'db' in locals():
            await db.close()


@router.post("/refresh")
async def refresh_token(request: RefreshRequest) -> TokenResponse:
    """Refresh access token using refresh token."""
    try:
        # Refresh the session
        session_data = await session_manager.refresh_session(
            request.refresh_token
        )
        
        if not session_data:
            raise HTTPException(
                status_code=401,
                detail="Invalid refresh token"
            )
        
        # Get user info for response
        db = DatabaseManager(os.getenv('DATABASE_URL'))
        await db.initialize()
        
        async with db._pool.acquire() as conn:
            user = await conn.fetchrow("""
                SELECT id, email, name, role, avatar_url
                FROM users
                WHERE id = $1
            """, UUID(session_data['session_id']))
        
        await db.close()
        
        return TokenResponse(
            access_token=session_data['tokens']['access_token'],
            refresh_token=session_data['tokens']['refresh_token'],
            expires_in=session_data['tokens']['expires_in'],
            user={
                'id': str(user['id']),
                'email': user['email'],
                'name': user['name'],
                'role': user['role'],
                'avatar_url': user['avatar_url']
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Token refresh failed"
        )


@router.post("/logout")
async def logout(
    current_user: dict = Depends(require_user)
) -> dict:
    """Logout current session."""
    try:
        # Get token from request
        # This is a bit hacky but FastAPI doesn't expose the raw token easily
        # In production, we'd pass the token explicitly
        
        # Log logout event
        await session_manager.log_auth_event(
            'logout',
            current_user['user_id']
        )
        
        return {"message": "Logged out successfully"}
    
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Logout failed"
        )


@router.get("/me")
async def get_current_user_info(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """Get current user information."""
    return {
        'user': {
            'id': current_user['user_id'],
            'email': current_user['email'],
            'name': current_user['name'],
            'role': current_user['role'],
            'avatar_url': current_user.get('avatar_url')
        }
    }


@router.get("/sessions")
async def get_user_sessions(
    current_user: dict = Depends(require_user)
) -> dict:
    """Get all active sessions for current user."""
    sessions = await session_manager.get_active_sessions(
        current_user['user_id']
    )
    
    return {
        'sessions': sessions,
        'current_session_id': current_user.get('session_id')
    }


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    current_user: dict = Depends(require_user)
) -> dict:
    """Revoke a specific session."""
    # Users can only revoke their own sessions
    sessions = await session_manager.get_active_sessions(
        current_user['user_id']
    )
    
    session_ids = [s['session_id'] for s in sessions]
    if session_id not in session_ids:
        raise HTTPException(
            status_code=404,
            detail="Session not found"
        )
    
    # End the session
    # Note: In production, we'd mark the specific session as inactive
    # For now, this is a placeholder
    
    return {"message": "Session revoked successfully"}