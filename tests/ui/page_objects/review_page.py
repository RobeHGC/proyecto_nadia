"""
Review Page Object for NADIA UI Testing

This module provides page object for the review interface,
including review approval, editing, and review workflow functionality.
"""
from typing import List, Dict, Optional
from .base_page import BasePage


class ReviewPage(BasePage):
    """Page object for the NADIA review interface."""
    
    @property
    def page_url(self) -> str:
        return "/#reviews"  # Tab-based navigation
    
    @property
    def page_title_selector(self) -> str:
        return ".review-header, [data-testid='review-header'], h2"
    
    @property
    def loading_indicator_selector(self) -> str:
        return ".review-loading, .loading-reviews"
    
    # Review item selectors
    REVIEW_ITEMS = ".review-item, [data-testid='review-item']"
    SELECTED_REVIEW = ".review-item.selected, .review-item.active"
    
    # Review details selectors
    USER_MESSAGE = ".user-message, [data-testid='user-message']"
    AI_RESPONSE = ".ai-response, [data-testid='ai-response']"
    REVIEWER_NOTES = ".reviewer-notes, [data-testid='reviewer-notes']"
    
    # Action buttons
    APPROVE_BUTTON = ".approve-btn, [data-action='approve']"
    REJECT_BUTTON = ".reject-btn, [data-action='reject']"
    EDIT_BUTTON = ".edit-btn, [data-action='edit']"
    SAVE_BUTTON = ".save-btn, [data-action='save']"
    CANCEL_BUTTON = ".cancel-btn, [data-action='cancel']"
    
    # Edit mode selectors
    EDIT_TEXTAREA = "#final-bubbles, .edit-textarea, [data-testid='edit-textarea']"
    EDIT_TAGS = ".edit-tags, [data-testid='edit-tags']"
    QUALITY_SCORE = ".quality-score, [data-testid='quality-score']"
    
    # Batch operations
    SELECT_ALL_CHECKBOX = ".select-all, [data-action='select-all']"
    REVIEW_CHECKBOXES = ".review-checkbox, [data-testid='review-checkbox']"
    BATCH_APPROVE_BUTTON = ".batch-approve, [data-action='batch-approve']"
    BATCH_REJECT_BUTTON = ".batch-reject, [data-action='batch-reject']"
    
    async def get_review_count(self) -> int:
        """Get total number of reviews in the queue."""
        return await self.count_elements(self.REVIEW_ITEMS)
    
    async def select_review(self, review_id: str = None, index: int = None) -> bool:
        """
        Select a review by ID or index.
        
        Args:
            review_id: Specific review ID to select
            index: Zero-based index of review to select (if no ID provided)
        """
        if review_id:
            selector = f"[data-review-id='{review_id}']"
        elif index is not None:
            selector = f"{self.REVIEW_ITEMS}:nth-child({index + 1})"
        else:
            # Select first review
            selector = f"{self.REVIEW_ITEMS}:first-child"
        
        success = await self.click_element(selector)
        if success:
            # Wait for review details to load
            await self.wait_for_element(self.USER_MESSAGE)
        return success
    
    async def get_selected_review_id(self) -> Optional[str]:
        """Get the ID of the currently selected review."""
        if not await self.is_element_visible(self.SELECTED_REVIEW):
            return None
        
        return await self.get_element_attribute(self.SELECTED_REVIEW, "data-review-id")
    
    async def get_review_details(self, review_id: str = None) -> Dict[str, str]:
        """
        Get details of a review.
        
        Args:
            review_id: Specific review ID (if None, gets currently selected review)
        """
        if review_id:
            await self.select_review(review_id)
        
        details = {}
        
        # User message
        if await self.is_element_visible(self.USER_MESSAGE):
            details['user_message'] = await self.get_element_text(self.USER_MESSAGE)
        
        # AI response
        if await self.is_element_visible(self.AI_RESPONSE):
            details['ai_response'] = await self.get_element_text(self.AI_RESPONSE)
        
        # Reviewer notes
        if await self.is_element_visible(self.REVIEWER_NOTES):
            details['reviewer_notes'] = await self.get_element_text(self.REVIEWER_NOTES)
        
        # Additional metadata
        script = """
        const selectedReview = document.querySelector('.review-item.selected, .review-item.active');
        if (!selectedReview) return {};
        
        return {
            timestamp: selectedReview.querySelector('.timestamp')?.textContent?.trim() || '',
            user_id: selectedReview.querySelector('.user-id')?.textContent?.trim() || '',
            risk_score: selectedReview.querySelector('.risk-score')?.textContent?.trim() || '',
            llm_model: selectedReview.querySelector('.llm-model')?.textContent?.trim() || '',
            cache_ratio: selectedReview.querySelector('.cache-ratio')?.textContent?.trim() || ''
        };
        """
        
        metadata = await self.browser.evaluate(script)
        if metadata:
            details.update(metadata)
        
        return details
    
    async def approve_review(self, review_id: str = None, wait_for_completion: bool = True) -> bool:
        """
        Approve a review.
        
        Args:
            review_id: Specific review ID (if None, approves currently selected)
            wait_for_completion: Whether to wait for approval to complete
        """
        if review_id:
            await self.select_review(review_id)
        
        if not await self.is_element_visible(self.APPROVE_BUTTON):
            return False
        
        success = await self.click_element(self.APPROVE_BUTTON, wait_for_response=wait_for_completion)
        
        if success and wait_for_completion:
            # Wait for approval confirmation or review to disappear
            await self.wait_for_element_to_disappear(self.SELECTED_REVIEW, timeout=10000)
        
        return success
    
    async def reject_review(self, review_id: str = None, wait_for_completion: bool = True) -> bool:
        """
        Reject a review.
        
        Args:
            review_id: Specific review ID (if None, rejects currently selected)
            wait_for_completion: Whether to wait for rejection to complete
        """
        if review_id:
            await self.select_review(review_id)
        
        if not await self.is_element_visible(self.REJECT_BUTTON):
            return False
        
        success = await self.click_element(self.REJECT_BUTTON, wait_for_response=wait_for_completion)
        
        if success and wait_for_completion:
            # Wait for rejection confirmation or review to disappear
            await self.wait_for_element_to_disappear(self.SELECTED_REVIEW, timeout=10000)
        
        return success
    
    async def enter_edit_mode(self, review_id: str = None) -> bool:
        """Enter edit mode for a review."""
        if review_id:
            await self.select_review(review_id)
        
        if not await self.is_element_visible(self.EDIT_BUTTON):
            return False
        
        success = await self.click_element(self.EDIT_BUTTON)
        
        if success:
            # Wait for edit interface to appear
            await self.wait_for_element(self.EDIT_TEXTAREA)
        
        return success
    
    async def edit_review_response(self, new_response: str, save: bool = True) -> bool:
        """
        Edit the review response text.
        
        Args:
            new_response: New response text
            save: Whether to save the changes immediately
        """
        if not await self.is_element_visible(self.EDIT_TEXTAREA):
            # Try to enter edit mode first
            if not await self.enter_edit_mode():
                return False
        
        # Clear and fill new response
        success = await self.fill_input(self.EDIT_TEXTAREA, new_response)
        
        if success and save:
            return await self.save_edit()
        
        return success
    
    async def add_reviewer_notes(self, notes: str, save: bool = True) -> bool:
        """
        Add or edit reviewer notes.
        
        Args:
            notes: Reviewer notes text
            save: Whether to save immediately
        """
        notes_field = f"{self.REVIEWER_NOTES} textarea, .reviewer-notes-input"
        
        if not await self.is_element_visible(notes_field):
            return False
        
        success = await self.fill_input(notes_field, notes)
        
        if success and save:
            # Try to save if in edit mode, or look for a save button
            if await self.is_element_visible(self.SAVE_BUTTON):
                return await self.save_edit()
            else:
                # Auto-save or blur to save
                await self.browser.evaluate(f"document.querySelector('{notes_field}').blur();")
        
        return success
    
    async def set_quality_score(self, score: int, save: bool = True) -> bool:
        """
        Set the quality score for a review.
        
        Args:
            score: Quality score (typically 1-5)
            save: Whether to save immediately
        """
        quality_input = f"{self.QUALITY_SCORE} input, .quality-score-input"
        quality_select = f"{self.QUALITY_SCORE} select, .quality-score-select"
        
        # Try input field first
        if await self.is_element_visible(quality_input):
            success = await self.fill_input(quality_input, str(score))
        # Try dropdown/select
        elif await self.is_element_visible(quality_select):
            success = await self.select_dropdown_option(quality_select, str(score))
        else:
            return False
        
        if success and save and await self.is_element_visible(self.SAVE_BUTTON):
            return await self.save_edit()
        
        return success
    
    async def save_edit(self) -> bool:
        """Save the current edit."""
        if not await self.is_element_visible(self.SAVE_BUTTON):
            return False
        
        return await self.click_element(self.SAVE_BUTTON, wait_for_response=True)
    
    async def cancel_edit(self) -> bool:
        """Cancel the current edit."""
        if not await self.is_element_visible(self.CANCEL_BUTTON):
            return False
        
        return await self.click_element(self.CANCEL_BUTTON)
    
    async def use_keyboard_shortcuts(self, action: str) -> bool:
        """
        Use keyboard shortcuts for review actions.
        
        Args:
            action: 'approve' (Ctrl+Enter), 'cancel' (Escape), 'edit' (E), etc.
        """
        shortcuts = {
            'approve': ('Control+Enter',),
            'save': ('Control+Enter',),
            'cancel': ('Escape',),
            'edit': ('e',),
            'next': ('ArrowDown',),
            'previous': ('ArrowUp',)
        }
        
        if action not in shortcuts:
            return False
        
        # For modifier keys like Ctrl+Enter
        if '+' in shortcuts[action][0]:
            modifier, key = shortcuts[action][0].split('+')
            script = f"""
            const event = new KeyboardEvent('keydown', {{
                key: '{key}',
                code: '{key}',
                ctrlKey: {modifier.lower() == 'control'},
                altKey: {modifier.lower() == 'alt'},
                shiftKey: {modifier.lower() == 'shift'},
                bubbles: true,
                cancelable: true
            }});
            document.dispatchEvent(event);
            """
        else:
            key = shortcuts[action][0]
            script = f"""
            const event = new KeyboardEvent('keydown', {{
                key: '{key}',
                code: '{key}',
                bubbles: true,
                cancelable: true
            }});
            document.dispatchEvent(event);
            """
        
        result = await self.browser.evaluate(script)
        return True
    
    async def select_multiple_reviews(self, review_ids: List[str] = None, 
                                    select_all: bool = False) -> bool:
        """
        Select multiple reviews for batch operations.
        
        Args:
            review_ids: List of specific review IDs to select
            select_all: Whether to select all reviews
        """
        if select_all:
            if await self.is_element_visible(self.SELECT_ALL_CHECKBOX):
                return await self.click_element(self.SELECT_ALL_CHECKBOX)
            else:
                # Select all manually
                checkboxes = await self.browser.evaluate(f"""
                document.querySelectorAll('{self.REVIEW_CHECKBOXES}');
                """)
                for checkbox in checkboxes or []:
                    await self.click_element(f"{self.REVIEW_CHECKBOXES}:nth-child({checkbox})")
                return True
        
        if review_ids:
            for review_id in review_ids:
                checkbox_selector = f"[data-review-id='{review_id}'] {self.REVIEW_CHECKBOXES}"
                await self.click_element(checkbox_selector)
            return True
        
        return False
    
    async def batch_approve_selected(self) -> bool:
        """Approve all selected reviews."""
        if not await self.is_element_visible(self.BATCH_APPROVE_BUTTON):
            return False
        
        return await self.click_element(self.BATCH_APPROVE_BUTTON, wait_for_response=True)
    
    async def batch_reject_selected(self) -> bool:
        """Reject all selected reviews."""
        if not await self.is_element_visible(self.BATCH_REJECT_BUTTON):
            return False
        
        return await self.click_element(self.BATCH_REJECT_BUTTON, wait_for_response=True)
    
    async def get_selected_review_count(self) -> int:
        """Get count of currently selected reviews."""
        script = f"""
        const checkboxes = document.querySelectorAll('{self.REVIEW_CHECKBOXES}:checked');
        return checkboxes.length;
        """
        
        result = await self.browser.evaluate(script)
        return int(result) if result is not None else 0
    
    async def clear_all_selections(self) -> bool:
        """Clear all review selections."""
        # If there's a "select all" checkbox, uncheck it
        if await self.is_element_visible(self.SELECT_ALL_CHECKBOX):
            select_all_checked = await self.browser.evaluate(f"""
            document.querySelector('{self.SELECT_ALL_CHECKBOX}').checked;
            """)
            
            if select_all_checked:
                return await self.click_element(self.SELECT_ALL_CHECKBOX)
        
        # Otherwise, uncheck all individual checkboxes
        script = f"""
        const checkboxes = document.querySelectorAll('{self.REVIEW_CHECKBOXES}:checked');
        checkboxes.forEach(cb => cb.click());
        return checkboxes.length;
        """
        
        result = await self.browser.evaluate(script)
        return True
    
    async def wait_for_review_load(self, timeout: int = 10000) -> bool:
        """Wait for reviews to load in the interface."""
        await self.wait_for_page_load()
        
        # Wait for either review items to appear or empty state
        try:
            await self.wait_for_element(self.REVIEW_ITEMS, timeout=timeout)
            return True
        except:
            # Check for empty state
            empty_state = ".empty-reviews, [data-testid='no-reviews']"
            if await self.is_element_visible(empty_state):
                return True
            return False
    
    async def get_review_statistics(self) -> Dict[str, int]:
        """Get review queue statistics."""
        stats = {}
        
        # Count total reviews
        stats['total'] = await self.get_review_count()
        
        # Count selected reviews
        stats['selected'] = await self.get_selected_review_count()
        
        # Get additional stats from the interface
        script = """
        const stats = {};
        
        // Look for stat elements
        const statElements = document.querySelectorAll('.review-stat, [data-stat]');
        statElements.forEach(element => {
            const key = element.getAttribute('data-stat') || 
                       element.className.match(/stat-(\w+)/)?.[1] ||
                       'unknown';
            const value = parseInt(element.textContent.trim()) || 0;
            stats[key] = value;
        });
        
        return stats;
        """
        
        additional_stats = await self.browser.evaluate(script)
        if additional_stats:
            stats.update(additional_stats)
        
        return stats